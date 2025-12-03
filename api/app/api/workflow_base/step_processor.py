"""
Process voice input for workflow steps.
"""

import io
import logging
from typing import Callable, Optional

from fastapi import UploadFile
from openai import OpenAI
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class VoiceStepProcessor:
    """Process voice input for workflow steps."""

    def __init__(self, openai_api_key: str):
        self.client = OpenAI(api_key=openai_api_key)

    async def transcribe_audio(self, audio_file: UploadFile) -> str:
        """Transcribe audio file using Whisper."""
        try:
            # Read audio into memory
            audio_content = await audio_file.read()
            audio_io = io.BytesIO(audio_content)
            audio_io.name = audio_file.filename or "audio.webm"

            # Reset for potential reuse
            await audio_file.seek(0)

            # Transcribe
            response = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_io,
                language="en",
            )

            transcript = response.text.strip()
            logger.info(f"Transcribed: {transcript[:50]}...")
            return transcript

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            raise ValueError("Failed to transcribe audio. Please try again.") from e

    async def parse_with_gpt(
        self, transcript: str, system_prompt: str, response_model: type[BaseModel]
    ) -> BaseModel:
        """Parse transcript using GPT with structured output."""
        try:
            response = self.client.beta.chat.completions.parse(
                model="gpt-4o-2024-08-06",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": transcript},
                ],
                response_format=response_model,
            )

            result = response.choices[0].message.parsed
            if not result:
                raise ValueError("Could not parse response")

            return result

        except Exception as e:
            logger.error(f"GPT parsing error: {e}")
            raise ValueError("Failed to understand input. Please try again.") from e

    async def process_voice_input(
        self,
        audio_file: UploadFile,
        system_prompt: str,
        response_model: type[BaseModel],
        validator: Optional[Callable] = None,
    ) -> tuple[str, BaseModel]:
        """Complete voice processing pipeline."""
        # Transcribe
        transcript = await self.transcribe_audio(audio_file)

        # Parse with GPT
        parsed_data = await self.parse_with_gpt(transcript, system_prompt, response_model)

        # Optional validation
        if validator:
            validator(parsed_data)

        return transcript, parsed_data
