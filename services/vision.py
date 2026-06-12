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
        from google.cloud import vision
        if settings.google_application_credentials:
            _client = vision.ImageAnnotatorClient.from_service_account_json(
                settings.google_application_credentials
            )
        else:
            _client = vision.ImageAnnotatorClient()
        return _client
    except Exception as e:
        logger.warning("Vision API client not available: %s", e)
        return None


async def ocr_handwriting(image_data: bytes) -> dict[str, Any]:
    client = _get_client()
    if client is None:
        return {"error": "Vision API client not configured", "text": ""}

    try:
        from google.cloud.vision_v1 import types

        image = types.Image(content=image_data)

        language_hints = [
            lang.strip()
            for lang in settings.ocr_language_hints.split(",")
            if lang.strip()
        ]

        image_context = types.ImageContext(
            language_hints=language_hints if language_hints else None
        )

        response = client.text_detection(
            image=image,
            image_context=image_context,
        )

        if response.error.message:
            logger.error("Vision API error: %s", response.error.message)
            return {"error": response.error.message, "text": ""}

        annotations = response.text_annotations

        full_text = annotations[0].description if annotations else ""

        words = []
        try:
            if response.full_text_annotation:
                for page in response.full_text_annotation.pages:
                    for block in page.blocks:
                        for paragraph in block.paragraphs:
                            for word in paragraph.words:
                                word_text = "".join(
                                    symbol.text for symbol in word.symbols
                                )
                                words.append({
                                    "text": word_text,
                                    "confidence": round(word.confidence, 4),
                                })
        except Exception:
            pass

        result = {
            "text": full_text,
            "words": words,
            "word_count": len(words),
            "confidence": round(
                sum(w["confidence"] for w in words) / len(words), 4
            ) if words else 0.0,
        }

        logger.info(
            "OCR completed: %d characters, %d words",
            len(full_text), len(words),
        )
        return result

    except Exception as e:
        logger.error("OCR processing failed: %s", e)
        return {"error": str(e), "text": ""}
