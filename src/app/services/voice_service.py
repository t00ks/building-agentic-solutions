"""
Voice service module for handling speech-to-text and text-to-speech operations.

This module provides a unified interface for Azure OpenAI voice capabilities including:
- Speech-to-Text (STT) transcription using Whisper model
- Text-to-Speech (TTS) synthesis using Azure OpenAI TTS models

The service is designed to be modular and replaceable, allowing easy swapping
of underlying providers or models.
"""

import io
from functools import lru_cache
from typing import BinaryIO, Literal

from openai import AzureOpenAI

from core.config import get_config
from core.exceptions import AgentResourceError
from core.logging_config import get_logger
from services.llm_service import get_voice_client

# Type definitions for TTS voices
TTSVoice = Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"]


class VoiceService:
    """
    Service for handling voice interactions using Azure OpenAI.
    
    This service provides methods for:
    - Transcribing audio to text (Speech-to-Text)
    - Synthesizing speech from text (Text-to-Speech)
    
    All methods use Azure OpenAI API endpoints and require proper configuration
    in the environment variables.
    """

    def __init__(self):
        """Initialize the VoiceService with Azure OpenAI client."""
        self.logger = get_logger(__name__)
        self.config = get_config()
        self._client: AzureOpenAI | None = None

    @property
    def client(self) -> AzureOpenAI:
        """
        Get or create the Azure OpenAI client instance.
        
        Returns:
            AzureOpenAI: Configured client for Azure OpenAI API.
            
        Raises:
            AgentResourceError: If client initialization fails.
        """
        if self._client is None:
            self._client = get_voice_client()
        return self._client

    async def transcribe_audio(
        self,
        audio_file: BinaryIO,
        filename: str = "audio.webm",
        language: str | None = None,
    ) -> str:
        """
        Transcribe audio to text using Azure OpenAI Whisper model.
        
        Args:
            audio_file: Binary audio file object (supports multiple formats: webm, mp3, wav, etc.)
            filename: Name of the audio file (used for format detection)
            language: Optional language code (e.g., 'en', 'es'). If None, auto-detects.
            
        Returns:
            str: Transcribed text from the audio.
            
        Raises:
            AgentResourceError: If transcription fails.
            
        Example:
            ```python
            with open("recording.webm", "rb") as audio:
                text = await voice_service.transcribe_audio(audio, "recording.webm")
                print(f"Transcribed: {text}")
            ```
        """
        try:
            self.logger.info(f"Starting transcription for audio file: {filename}")
            
            # Prepare the audio file with proper filename for format detection
            audio_file.name = filename
            
            # Call Azure OpenAI Whisper API TODO:: Update this to support AWS
            params = {
                "model": self.config.azure.speech_stt_deployment or "whisper-1",
                "file": audio_file,
            }
            
            if language:
                params["language"] = language
            
            transcript = self.client.audio.transcriptions.create(**params)
            
            transcribed_text = transcript.text
            self.logger.info(f"Successfully transcribed audio: {len(transcribed_text)} characters")
            
            return transcribed_text
            
        except Exception as e:
            self.logger.error(f"Transcription failed: {e}", exc_info=True)
            raise AgentResourceError(f"Failed to transcribe audio: {e}") from e

    async def synthesize_speech(
        self,
        text: str,
        voice: TTSVoice = "alloy",
        speed: float = 1.0,
    ) -> bytes:
        """
        Synthesize speech from text using Azure OpenAI TTS model.
        
        Args:
            text: Text to convert to speech.
            voice: Voice to use for synthesis. Options: alloy, echo, fable, onyx, nova, shimmer.
            speed: Speed of speech (0.25 to 4.0). Default is 1.0 (normal speed).
            
        Returns:
            bytes: Audio data in MP3 format.
            
        Raises:
            AgentResourceError: If synthesis fails.
            
        Example:
            ```python
            audio_data = await voice_service.synthesize_speech(
                "Hello, how can I help you today?",
                voice="nova"
            )
            with open("response.mp3", "wb") as f:
                f.write(audio_data)
            ```
        """
        try:
            self.logger.info(f"Starting speech synthesis for {len(text)} characters with voice: {voice}")
            
            # Validate speed parameter
            if not 0.25 <= speed <= 4.0:
                raise ValueError(f"Speed must be between 0.25 and 4.0, got {speed}")
            
            # Call Azure OpenAI TTS API
            response = self.client.audio.speech.create(
                model=self.config.azure.speech_tts_deployment or "tts-1",
                voice=voice,
                input=text,
                speed=speed,
            )
            
            # Read audio content
            audio_data = response.content
            
            self.logger.info(f"Successfully synthesized speech: {len(audio_data)} bytes")
            
            return audio_data
            
        except ValueError as e:
            self.logger.error(f"Invalid parameter: {e}")
            raise AgentResourceError(f"Invalid synthesis parameter: {e}") from e
        except Exception as e:
            self.logger.error(f"Speech synthesis failed: {e}", exc_info=True)
            raise AgentResourceError(f"Failed to synthesize speech: {e}") from e