"""
Voice processing and structured output parsing for invoice workflow steps.
"""

import io
import logging

from fastapi import UploadFile
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from .models import (
    InvoiceContactNameStep,
    InvoiceDueDateStep,
    InvoiceLineItemStep,
    StepValidationError,
)
from .validators import (
    sanitize_name,
)

logger = logging.getLogger(__name__)

# Maximum allowed audio file size (10MB)
MAX_AUDIO_SIZE = 10 * 1024 * 1024


async def transcribe_audio(client: OpenAI, audio_file: UploadFile) -> str:
    """Transcribe audio file using OpenAI Whisper."""
    try:
        # Check file size if available
        if hasattr(audio_file, "size") and audio_file.size and audio_file.size > MAX_AUDIO_SIZE:
            raise StepValidationError(
                field="audio",
                message="Audio file too large. Please keep recordings under 10MB.",
            )

        # Read the audio file into memory
        audio_content = await audio_file.read()

        # Validate content size after reading
        if len(audio_content) > MAX_AUDIO_SIZE:
            raise StepValidationError(
                field="audio",
                message="Audio file too large. Please keep recordings under 10MB.",
            )

        audio_io = io.BytesIO(audio_content)
        audio_io.name = audio_file.filename or "audio.webm"

        # Reset file pointer for potential reuse
        await audio_file.seek(0)

        # Transcribe using Whisper
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_io,
            language="en",
        )

        transcript = response.text.strip()
        logger.info(f"Transcribed audio: {transcript[:100]}...")
        return transcript

    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
        raise StepValidationError(
            field="audio",
            message="Failed to transcribe audio. Please try speaking again.",
        ) from e


async def process_voice_step(
    audio_file: UploadFile,
    step: str,
    openai_api_key: str,
) -> tuple[str, BaseModel]:
    """Process voice input for current step using structured outputs."""

    # Initialize OpenAI client
    client = OpenAI(api_key=openai_api_key)

    # Transcribe audio
    transcript = await transcribe_audio(client, audio_file)

    # Process based on step
    try:
        if step == "contact_name":
            return await _parse_contact_name_step(client, transcript)
        elif step == "due_date":
            return await _parse_due_date_step(client, transcript)
        elif step == "line_item":
            return await _parse_line_item_step(client, transcript)
        else:
            raise ValueError(f"Unknown voice step: {step}")
    except ValidationError as e:
        # Extract the most relevant error
        error_detail = e.errors()[0] if e.errors() else {"msg": "Validation failed"}
        raise StepValidationError(
            field=error_detail.get("loc", ["unknown"])[0],
            message=error_detail.get("msg", "Please provide valid information"),
            partial_data={"transcript": transcript},
        ) from e


async def _parse_contact_name_step(
    client: OpenAI, transcript: str
) -> tuple[str, InvoiceContactNameStep]:
    """Parse contact name from transcript using structured output."""

    system_prompt = """Extract the contact or organization name from the user's speech.
    Determine if it's an organization based on keywords like 'company', 'limited', 'ltd', 
    'corporation', 'inc', 'services', 'solutions', or similar business terms."""

    response = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcript},
        ],
        response_format=InvoiceContactNameStep,
    )

    result = response.choices[0].message.parsed
    if not result:
        raise StepValidationError(
            field="contact_name",
            message="Could not understand the name. Please speak clearly.",
            partial_data={"transcript": transcript},
        )

    # Validate and sanitize the name
    try:
        sanitized_name = sanitize_name(result.contact_name)
        result.contact_name = sanitized_name
    except ValueError as e:
        raise StepValidationError(
            field="contact_name",
            message=str(e),
            partial_data={"transcript": transcript},
        ) from e

    logger.info(f"Parsed contact name: {result.contact_name}, is_org: {result.is_organization}")
    return transcript, result


async def _parse_due_date_step(client: OpenAI, transcript: str) -> tuple[str, InvoiceDueDateStep]:
    """Parse due date from transcript using structured output."""
    from datetime import datetime

    system_prompt = f"""Extract the invoice due date from the user's speech.
    Handle both specific dates and relative dates:
    - Specific dates: "December 31st", "31st of December", "12/31/2024"
    - Relative dates: "in 30 days", "next month", "end of month", "in two weeks"
    
    For relative dates, also provide the number of days from today if possible.
    Today's date for reference: {datetime.now().date()}
    """

    response = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcript},
        ],
        response_format=InvoiceDueDateStep,
    )

    result = response.choices[0].message.parsed
    if not result:
        raise StepValidationError(
            field="due_date",
            message="Could not understand the due date. Please try again.",
            partial_data={"transcript": transcript},
        )

    logger.info(f"Parsed due date: {result.due_date}")
    return transcript, result


async def _parse_line_item_step(client: OpenAI, transcript: str) -> tuple[str, InvoiceLineItemStep]:
    """Parse line item details from transcript using structured output."""

    system_prompt = """Extract line item details from the user's speech.
    
    Listen for:
    - Description: What is being invoiced (services, products, etc.)
    - Quantity: How many units (default to 1 if not mentioned)
    - Unit price: The price per unit
    - VAT rate keywords:
      * "standard rate", "20 percent VAT", "normal VAT" → vat_rate: "standard" (20%)
      * "reduced rate", "5 percent VAT" → vat_rate: "reduced" (5%)
      * "zero rated", "no VAT", "0 percent" → vat_rate: "zero_rated" (0%)
      * "exempt", "VAT exempt" → vat_rate: "exempt"
    - Account code patterns:
      * "sales", "revenue" → account_code: "200"
      * "services" → account_code: "201"
      * "consulting" → account_code: "202"
    
    Default to:
    - quantity: 1 if not specified
    - vat_rate: "standard" if no VAT mentioned
    - account_code: "200" if not specified
    
    Example: "10 hours of consulting at 150 pounds per hour, standard rate VAT"
    → description: "Consulting", quantity: 10, unit_price: 150, vat_rate: "standard"
    """

    response = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcript},
        ],
        response_format=InvoiceLineItemStep,
    )

    result = response.choices[0].message.parsed
    if not result:
        raise StepValidationError(
            field="line_item",
            message="Could not understand the line item details. Please describe what you're invoicing, the quantity, and price.",
            partial_data={"transcript": transcript},
        )

    logger.info(
        f"Parsed line item: {result.description}, qty: {result.quantity}, price: {result.unit_price}, VAT: {result.vat_rate}"
    )
    return transcript, result
