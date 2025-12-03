"""
Voice processing and structured output parsing for contact workflow steps.
"""

import io
import logging

from fastapi import UploadFile
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from .models import (
    ContactAddressStep,
    ContactConfirmation,
    ContactEmailStep,
    ContactNameStep,
    StepValidationError,
)
from .validators import (
    sanitize_address_line,
    sanitize_city,
    sanitize_country_code,
    sanitize_email,
    sanitize_name,
    sanitize_postal_code,
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
        )


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
        if step == "name":
            return await _parse_name_step(client, transcript)
        elif step == "email":
            return await _parse_email_step(client, transcript)
        elif step == "address":
            return await _parse_address_step(client, transcript)
        elif step == "confirmation":
            return await _parse_confirmation_step(client, transcript)
        else:
            raise ValueError(f"Unknown step: {step}")
    except ValidationError as e:
        # Extract the most relevant error
        error_detail = e.errors()[0] if e.errors() else {"msg": "Validation failed"}
        raise StepValidationError(
            field=error_detail.get("loc", ["unknown"])[0],
            message=error_detail.get("msg", "Please provide valid information"),
            partial_data={"transcript": transcript},
        )


async def _parse_name_step(client: OpenAI, transcript: str) -> tuple[str, ContactNameStep]:
    """Parse name from transcript using structured output."""

    system_prompt = """Extract the contact or organization name from the user's speech.
    Determine if it's an organization based on keywords like 'company', 'limited', 'ltd', 
    'corporation', 'inc', 'services', 'solutions', or similar business terms."""

    response = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcript},
        ],
        response_format=ContactNameStep,
    )

    result = response.choices[0].message.parsed
    if not result:
        raise StepValidationError(
            field="name",
            message="Could not understand the name. Please speak clearly.",
            partial_data={"transcript": transcript},
        )

    # Validate and sanitize the name
    try:
        sanitized_name = sanitize_name(result.name)
        result.name = sanitized_name
    except ValueError as e:
        raise StepValidationError(
            field="name",
            message=str(e),
            partial_data={"transcript": transcript},
        )

    logger.info(f"Parsed name: {result.name}, is_org: {result.is_organization}")
    return transcript, result


async def _parse_email_step(client: OpenAI, transcript: str) -> tuple[str, ContactEmailStep]:
    """Parse email address from transcript using structured output."""

    system_prompt = """Extract the email address from the user's speech.
    Common patterns to handle:
    - 'at' means '@'
    - 'dot' means '.'
    - 'dash' or 'hyphen' means '-'
    - 'underscore' means '_'
    - Remove spaces from the email address
    - Convert to lowercase
    
    Example: "john dot smith at example dot com" -> "john.smith@example.com"
    """

    response = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcript},
        ],
        response_format=ContactEmailStep,
    )

    result = response.choices[0].message.parsed
    if not result:
        raise StepValidationError(
            field="email",
            message="Could not understand the email address. Please spell it out clearly.",
            partial_data={"transcript": transcript},
        )

    # Validate and sanitize the email
    try:
        sanitized_email = sanitize_email(result.email_address)
        result.email_address = sanitized_email
    except ValueError as e:
        raise StepValidationError(
            field="email",
            message=str(e),
            partial_data={"transcript": transcript},
        )

    logger.info(f"Parsed email: {result.email_address}")
    return transcript, result


async def _parse_address_step(client: OpenAI, transcript: str) -> tuple[str, ContactAddressStep]:
    """Parse address from transcript using structured output."""

    system_prompt = """Extract the complete address from the user's speech.
    Parse it into:
    - Street address (house number and street name)
    - City or town name
    - Postal code (UK postcodes like SW1A 1AA or US ZIP codes)
    
    Assume UK (GB) as the country unless specified otherwise.
    Clean up the postal code format appropriately.
    """

    response = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcript},
        ],
        response_format=ContactAddressStep,
    )

    result = response.choices[0].message.parsed
    if not result:
        raise StepValidationError(
            field="address",
            message="Could not understand the address. Please include street, city, and postal code.",
            partial_data={"transcript": transcript},
        )

    # Validate and sanitize the address components
    try:
        result.address_line1 = sanitize_address_line(result.address_line1)
        result.city = sanitize_city(result.city)
        result.postal_code = sanitize_postal_code(result.postal_code)
        result.country = sanitize_country_code(result.country)
    except ValueError as e:
        raise StepValidationError(
            field="address",
            message=str(e),
            partial_data={"transcript": transcript},
        )

    logger.info(f"Parsed address: {result.address_line1}, {result.city}, {result.postal_code}")
    return transcript, result


async def _parse_confirmation_step(
    client: OpenAI, transcript: str
) -> tuple[str, ContactConfirmation]:
    """Parse confirmation response from transcript."""

    system_prompt = """Determine if the user is confirming the contact details or requesting changes.
    Look for:
    - Confirmation words: "yes", "confirm", "correct", "looks good", "that's right"
    - Rejection/correction indicators: "no", "change", "wrong", "incorrect", "fix"
    
    If they mention specific corrections, extract them.
    """

    response = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcript},
        ],
        response_format=ContactConfirmation,
    )

    result = response.choices[0].message.parsed
    if not result:
        raise StepValidationError(
            field="confirmation",
            message="Could not understand your response. Please say 'confirm' or describe what needs to be changed.",
            partial_data={"transcript": transcript},
        )

    logger.info(f"Confirmation: {result.confirmed}, corrections: {result.corrections_needed}")
    return transcript, result
