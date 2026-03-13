"""
Voice router for handling voice interaction endpoints.

This module provides RESTful API endpoints for:
- Speech-to-Text transcription
- Text-to-Speech synthesis

These endpoints enable voice interaction capabilities for the chat interface.
"""

import io
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from core.exceptions import AgentResourceError
from core.logging_config import get_logger
from services.voice_service import TTSVoice, VoiceService

router = APIRouter(prefix="/voice", tags=["voice"])
logger = get_logger(__name__)


class TranscriptionResponse(BaseModel):
    """Response model for audio transcription."""
    
    text: str = Field(..., description="Transcribed text from the audio input")
    language: str | None = Field(None, description="Detected or specified language code")


class SynthesisRequest(BaseModel):
    """Request model for text-to-speech synthesis."""
    
    text: str = Field(..., description="Text to convert to speech", min_length=1, max_length=4096)
    voice: TTSVoice = Field("alloy", description="Voice to use for synthesis")
    speed: float = Field(1.0, description="Speed of speech (0.25 to 4.0)", ge=0.25, le=4.0)


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    audio: Annotated[UploadFile, File(description="Audio file to transcribe (supports webm, mp3, wav, etc.)")],
    language: Annotated[str | None, Form(description="Optional language code (e.g., 'en', 'es')")] = None,
) -> TranscriptionResponse:
    """
    Transcribe audio to text using Azure OpenAI Whisper model.
    
    This endpoint accepts an audio file and returns the transcribed text.
    The audio can be in various formats including webm, mp3, wav, m4a, etc.
    
    Args:
        audio: Audio file to transcribe (multipart/form-data)
        language: Optional language code for transcription
        
    Returns:
        TranscriptionResponse: Object containing the transcribed text
        
    Raises:
        HTTPException: 400 if audio file is invalid, 500 if transcription fails
        
    Example:
        ```bash
        curl -X POST "http://localhost:8000/voice/transcribe" \\
          -F "audio=@recording.webm" \\
          -F "language=en"
        ```
    """
    request_logger = logger.bind(
        filename=audio.filename,
        content_type=audio.content_type,
        language=language,
    )
    
    try:
        # Validate audio file
        if not audio.filename:
            raise HTTPException(status_code=400, detail="Audio file is required")
        
        # Read audio content
        audio_content = await audio.read()
        if not audio_content:
            raise HTTPException(status_code=400, detail="Audio file is empty")
        
        request_logger.info(f"Received audio for transcription: {len(audio_content)} bytes")
        
        # Create file-like object for the service
        audio_file = io.BytesIO(audio_content)
        
        # Get voice service and transcribe
        voice_service = VoiceService()
        transcribed_text = await voice_service.transcribe_audio(
            audio_file=audio_file,
            filename=audio.filename,
            language=language,
        )
        
        request_logger.info(f"Successfully transcribed audio: {len(transcribed_text)} characters")
        
        return TranscriptionResponse(
            text=transcribed_text,
            language=language,
        )
        
    except AgentResourceError as e:
        request_logger.error(f"Voice service error: {e.message}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e.message}") from None
    except HTTPException:
        raise
    except Exception as e:
        request_logger.error(f"Unexpected error during transcription: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred") from None


@router.post("/synthesize")
async def synthesize_speech(request: SynthesisRequest) -> Response:
    """
    Synthesize speech from text using Azure OpenAI TTS model.
    
    This endpoint accepts text and returns audio data in MP3 format.
    
    Args:
        request: Synthesis request containing text, voice, and speed parameters
        
    Returns:
        Response: Audio data in MP3 format with appropriate headers
        
    Raises:
        HTTPException: 400 if request is invalid, 500 if synthesis fails
        
    Example:
        ```bash
        curl -X POST "http://localhost:8000/voice/synthesize" \\
          -H "Content-Type: application/json" \\
          -d '{"text": "Hello world", "voice": "nova", "speed": 1.0}' \\
          --output response.mp3
        ```
    """
    request_logger = logger.bind(
        text_length=len(request.text),
        voice=request.voice,
        speed=request.speed,
    )
    
    try:
        request_logger.info("Starting speech synthesis")
        
        # Get voice service and synthesize
        voice_service = VoiceService()
        audio_data = await voice_service.synthesize_speech(
            text=request.text,
            voice=request.voice,
            speed=request.speed,
        )
        
        request_logger.info(f"Successfully synthesized speech: {len(audio_data)} bytes")
        
        # Return audio as MP3
        return Response(
            content=audio_data,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "attachment; filename=speech.mp3",
                "Cache-Control": "no-cache",
            },
        )
        
    except AgentResourceError as e:
        request_logger.error(f"Voice service error: {e.message}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Speech synthesis failed: {e.message}") from None
    except Exception as e:
        request_logger.error(f"Unexpected error during synthesis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred") from None


@router.get("/health")
async def voice_health_check() -> dict[str, str]:
    """
    Health check endpoint for voice services.
    
    This endpoint verifies that the voice service is properly configured
    and can be initialized.
    
    Returns:
        dict: Status information about the voice service
        
    Raises:
        HTTPException: 503 if voice service is not properly configured
    """
    try:
        voice_service = VoiceService()
        voice_service.client()
        return {
            "status": "healthy",
            "service": "voice",
            "message": "Voice service is configured and ready",
        }
    except AgentResourceError as e:
        logger.error(f"Voice service health check failed: {e.message}")
        raise HTTPException(
            status_code=503,
            detail=f"Voice service not available: {e.message}",
        ) from None