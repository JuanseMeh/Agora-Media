from __future__ import annotations

import logging
from typing import Any

from config.settings import settings

logger = logging.getLogger(__name__)


_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    try:
        from google.cloud import speech
        if settings.google_application_credentials:
            _client = speech.SpeechClient.from_service_account_json(
                settings.google_application_credentials
            )
        else:
            _client = speech.SpeechClient()
        return _client
    except Exception as e:
        logger.warning("Speech-to-Text client not available: %s", e)
        return None


async def transcribe_audio(
    audio_data: bytes,
    mime_type: str = "audio/webm",
    language_code: str = "es-ES",
) -> dict[str, Any]:
    client = _get_client()
    if client is None:
        return {"error": "Speech-to-Text client not configured", "text": ""}

    try:
        from google.cloud.speech_v1 import types

        audio = types.RecognitionAudio(content=audio_data)

        config = types.RecognitionConfig(
            encoding=types.RecognitionConfig.AudioEncoding.WEBM_OPUS,
            sample_rate_hertz=48000,
            language_code=language_code,
            enable_automatic_punctuation=True,
            enable_word_time_offsets=True,
            model="latest_long",
            alternative_language_codes=["en-US", "fr-FR", "pt-BR"],
        )

        if "webm" in mime_type:
            config.encoding = types.RecognitionConfig.AudioEncoding.WEBM_OPUS
        elif "wav" in mime_type:
            config.encoding = types.RecognitionConfig.AudioEncoding.LINEAR16
        elif "ogg" in mime_type:
            config.encoding = types.RecognitionConfig.AudioEncoding.OGG_OPUS
        elif "mp3" in mime_type:
            config.encoding = types.RecognitionConfig.AudioEncoding.MP3
        elif "flac" in mime_type:
            config.encoding = types.RecognitionConfig.AudioEncoding.FLAC

        response = client.recognize(config=config, audio=audio)

        if not response.results:
            return {"text": "", "transcript": "", "segments": [], "error": None}

        full_transcript = ""
        segments = []

        for result in response.results:
            best_alternative = result.alternatives[0]
            full_transcript += best_alternative.transcript + " "

            words = []
            if best_alternative.words:
                for word_info in best_alternative.words:
                    words.append({
                        "word": word_info.word,
                        "start_time": word_info.start_time.total_seconds(),
                        "end_time": word_info.end_time.total_seconds(),
                    })

            segments.append({
                "transcript": best_alternative.transcript,
                "confidence": round(best_alternative.confidence, 4),
                "words": words,
                "is_final": result.is_final,
            })

        full_transcript = full_transcript.strip()

        result = {
            "text": full_transcript,
            "transcript": full_transcript,
            "segments": segments,
            "language_code": language_code,
            "duration_seconds": sum(
                s["words"][-1]["end_time"] - s["words"][0]["start_time"]
                for s in segments if s["words"]
            ) if any(s["words"] for s in segments) else None,
            "error": None,
        }

        logger.info(
            "Transcription completed: %d chars, %d segments",
            len(full_transcript), len(segments),
        )
        return result

    except Exception as e:
        logger.error("Audio transcription failed: %s", e)
        return {"error": str(e), "text": ""}
