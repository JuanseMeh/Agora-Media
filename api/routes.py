from __future__ import annotations

import logging
import os
from typing import Any

import filetype
from fastapi import APIRouter, Depends, HTTPException, UploadFile

from api.dependencies import get_user_id
from db.queries import media_files as media_queries
from db.queries import media_links as link_queries
from schemas.models import (
    BatchProcessItem,
    BatchProcessRequest,
    BatchProcessResponse,
    ContentItem,
    CreateLinkRequest,
    EntityContentResponse,
    ErrorResponse,
    HealthResponse,
    MediaFileResponse,
    MediaLinkResponse,
    MediaLinkWithFileResponse,
    ProcessingResult,
    UploadResponse,
)
from services import document_parser, speech, storage, vision
from services.users_service import update_user_profile
from services.workspace_service import (
    link_file_to_assignment,
    link_file_to_submission,
)

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_FILE_SIZE = 100 * 1024 * 1024

SUPPORTED_MIME_CATEGORIES: dict[str, str] = {
    "image/jpeg": "image",
    "image/png": "image",
    "image/gif": "image",
    "image/webp": "image",
    "image/bmp": "image",
    "image/tiff": "image",
    "image/svg+xml": "image",
    "audio/mpeg": "audio",
    "audio/mp3": "audio",
    "audio/wav": "audio",
    "audio/ogg": "audio",
    "audio/webm": "audio",
    "audio/flac": "audio",
    "audio/aac": "audio",
    "audio/x-m4a": "audio",
    "video/mp4": "video",
    "video/webm": "video",
    "video/ogg": "video",
    "application/pdf": "document",
    "application/msword": "document",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "document",
    "application/vnd.ms-powerpoint": "document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "document",
    "text/plain": "document",
    "text/html": "document",
    "text/markdown": "document",
    "application/vnd.oasis.opendocument.text": "document",
}

ALLOWED_MIME_TYPES = set(SUPPORTED_MIME_CATEGORIES.keys())


def _detect_mime(data: bytes, original_filename: str) -> str | None:
    kind = filetype.guess_mime(data)
    if kind and kind in ALLOWED_MIME_TYPES:
        return kind
    _, ext = os.path.splitext(original_filename)
    ext = ext.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
        ".svg": "image/svg+xml",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".aac": "audio/aac",
        ".m4a": "audio/x-m4a",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".pdf": "application/pdf",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".ppt": "application/vnd.ms-powerpoint",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".txt": "text/plain",
        ".html": "text/html",
        ".htm": "text/html",
        ".md": "text/markdown",
    }
    return mime_map.get(ext)


def _media_category_from_mime(mime: str) -> str:
    return SUPPORTED_MIME_CATEGORIES.get(mime, "other")


def _serialize_media(row: dict[str, Any]) -> dict[str, Any]:
    import json
    metadata = row.get("metadata", {})
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "original_filename": row["original_filename"],
        "mime_type": row["mime_type"],
        "size_bytes": row["size_bytes"],
        "storage_path": row["storage_path"],
        "bucket_name": row["bucket_name"],
        "content_hash": row.get("content_hash"),
        "media_category": row["media_category"],
        "status": row["status"],
        "metadata": metadata,
        "width": row.get("width"),
        "height": row.get("height"),
        "duration_seconds": row.get("duration_seconds"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile,
    user_id: str = Depends(get_user_id),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size is {MAX_FILE_SIZE // (1024*1024)}MB.",
        )

    mime = _detect_mime(data, file.filename)
    if not mime:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.filename}",
        )

    category = _media_category_from_mime(mime)

    upload_result = await storage.upload_file(
        data=data,
        user_id=user_id,
        original_filename=file.filename,
        mime_type=mime,
        media_category=category,
    )

    width = None
    height = None
    if category == "image":
        try:
            from PIL import Image
            from io import BytesIO
            img = Image.open(BytesIO(data))
            width, height = img.size
        except Exception:
            pass

    media = await media_queries.create_media_file(
        user_id=user_id,
        original_filename=file.filename,
        mime_type=mime,
        size_bytes=upload_result["size_bytes"],
        storage_path=upload_result["storage_path"],
        bucket_name=upload_result["bucket_name"],
        content_hash=upload_result["content_hash"],
        media_category=category,
        width=width,
        height=height,
    )

    signed_url = await storage.get_signed_url(
        upload_result["storage_path"], upload_result["bucket_name"]
    )

    return UploadResponse(
        media=MediaFileResponse(**_serialize_media(media)),
        signed_url=signed_url,
    )


@router.get("/{media_id}", response_model=MediaFileResponse)
async def get_media(
    media_id: str,
    user_id: str = Depends(get_user_id),
):
    media = await media_queries.get_media_file(media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found.")
    if media["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    return MediaFileResponse(**_serialize_media(media))


@router.get("/{media_id}/download")
async def download_media(
    media_id: str,
    user_id: str = Depends(get_user_id),
):
    media = await media_queries.get_media_file(media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found.")
    if media["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied.")

    signed_url = await storage.get_signed_url(
        media["storage_path"], media["bucket_name"]
    )
    if not signed_url:
        raise HTTPException(status_code=500, detail="Failed to generate download URL.")
    return {"url": signed_url}


@router.delete("/{media_id}")
async def delete_media(
    media_id: str,
    user_id: str = Depends(get_user_id),
):
    media = await media_queries.get_media_file(media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found.")
    if media["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied.")

    await storage.delete_file(media["storage_path"], media["bucket_name"])
    await link_queries.delete_links_for_media(media_id)
    await media_queries.delete_media_file(media_id)
    return {"status": "deleted"}


@router.get("/list/my", response_model=list[MediaFileResponse])
async def list_my_media(
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user_id: str = Depends(get_user_id),
):
    rows = await media_queries.list_user_media(user_id, category, limit, offset)
    return [MediaFileResponse(**_serialize_media(r)) for r in rows]


@router.post("/{media_id}/process/ocr", response_model=ProcessingResult)
async def process_ocr(
    media_id: str,
    user_id: str = Depends(get_user_id),
):
    media = await media_queries.get_media_file(media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found.")
    if media["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if media["media_category"] not in ("image", "document"):
        raise HTTPException(status_code=400, detail="OCR only supported for images and documents.")

    await media_queries.update_media_status(media_id, "processing")

    file_data = await storage.download_file(media["storage_path"], media["bucket_name"])
    if not file_data:
        await media_queries.update_media_status(media_id, "failed")
        raise HTTPException(status_code=500, detail="Failed to read file for processing.")

    result = await vision.ocr_handwriting(file_data)

    if result.get("error"):
        await media_queries.update_media_status(media_id, "failed", {"ocr_error": result["error"]})
        return ProcessingResult(
            media_id=media_id,
            processing_type="ocr",
            status="failed",
            result=result,
        )

    await media_queries.update_media_status(
        media_id, "completed", {"ocr": result}
    )

    return ProcessingResult(
        media_id=media_id,
        processing_type="ocr",
        status="completed",
        result=result,
    )


@router.post("/{media_id}/process/transcribe", response_model=ProcessingResult)
async def process_transcribe(
    media_id: str,
    language_code: str = "es-ES",
    user_id: str = Depends(get_user_id),
):
    media = await media_queries.get_media_file(media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found.")
    if media["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if media["media_category"] not in ("audio", "video"):
        raise HTTPException(
            status_code=400, detail="Transcription only supported for audio and video."
        )

    await media_queries.update_media_status(media_id, "processing")

    file_data = await storage.download_file(media["storage_path"], media["bucket_name"])
    if not file_data:
        await media_queries.update_media_status(media_id, "failed")
        raise HTTPException(status_code=500, detail="Failed to read file for processing.")

    result = await speech.transcribe_audio(
        file_data,
        mime_type=media["mime_type"],
        language_code=language_code,
    )

    if result.get("error"):
        await media_queries.update_media_status(media_id, "failed", {"transcription_error": result["error"]})
        return ProcessingResult(
            media_id=media_id,
            processing_type="transcribe",
            status="failed",
            result=result,
        )

    await media_queries.update_media_status(
        media_id, "completed", {"transcription": result}
    )

    if result.get("duration_seconds"):
        await media_queries.update_media_metadata(
            media_id, {"duration_seconds": result["duration_seconds"]}
        )

    return ProcessingResult(
        media_id=media_id,
        processing_type="transcribe",
        status="completed",
        result=result,
    )


@router.post("/{media_id}/process/parse", response_model=ProcessingResult)
async def process_parse(
    media_id: str,
    user_id: str = Depends(get_user_id),
):
    media = await media_queries.get_media_file(media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found.")
    if media["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if media["media_category"] != "document":
        raise HTTPException(
            status_code=400, detail="Document parsing only supported for documents."
        )

    await media_queries.update_media_status(media_id, "processing")

    file_data = await storage.download_file(media["storage_path"], media["bucket_name"])
    if not file_data:
        await media_queries.update_media_status(media_id, "failed")
        raise HTTPException(status_code=500, detail="Failed to read file for processing.")

    result = await document_parser.parse_document_to_markdown(
        file_data,
        media["original_filename"],
        media["mime_type"],
    )

    if result.get("error"):
        await media_queries.update_media_status(media_id, "failed", {"parse_error": result["error"]})
        return ProcessingResult(
            media_id=media_id,
            processing_type="parse",
            status="failed",
            result=result,
        )

    await media_queries.update_media_status(
        media_id, "completed", {"document_parse": result}
    )

    return ProcessingResult(
        media_id=media_id,
        processing_type="parse",
        status="completed",
        result={"markdown": result["markdown"], "method": result.get("method")},
    )


@router.post("/link", response_model=MediaLinkResponse)
async def create_link(
    body: CreateLinkRequest,
    user_id: str = Depends(get_user_id),
):
    media = await media_queries.get_media_file(body.media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found.")
    if media["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied.")

    link = await link_queries.create_media_link(
        media_id=body.media_id,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        field_name=body.field_name,
    )

    if body.entity_type == "user_profile" and body.field_name == "avatar_url":
        signed_url = await storage.get_signed_url(
            media["storage_path"], media["bucket_name"]
        )
        if signed_url:
            await update_user_profile(user_id, signed_url)

    if body.entity_type == "submission":
        signed_url = await storage.get_signed_url(
            media["storage_path"], media["bucket_name"]
        )
        if signed_url:
            await link_file_to_submission(
                submission_id=int(body.entity_id),
                user_id=user_id,
                file_url=signed_url,
                file_name=media["original_filename"],
                file_type=media["mime_type"],
                file_size=media["size_bytes"],
            )

    if body.entity_type == "assignment":
        signed_url = await storage.get_signed_url(
            media["storage_path"], media["bucket_name"]
        )
        if signed_url:
            await link_file_to_assignment(
                assignment_id=int(body.entity_id),
                user_id=user_id,
                file_url=signed_url,
                file_name=media["original_filename"],
                file_type=media["mime_type"],
            )

    return MediaLinkResponse(**link)


@router.delete("/link/{link_id}")
async def delete_link(
    link_id: str,
    user_id: str = Depends(get_user_id),
):
    link = await link_queries.get_media_link_by_id(link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found.")

    media = await media_queries.get_media_file(link["media_id"])
    if media and media["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied.")

    deleted = await link_queries.delete_media_link(link_id)
    return {"status": "deleted"}


@router.get("/entity/{entity_type}/{entity_id}", response_model=list[MediaLinkWithFileResponse])
async def get_entity_media(
    entity_type: str,
    entity_id: str,
    user_id: str = Depends(get_user_id),
):
    links = await link_queries.get_links_for_entity(entity_type, entity_id)

    result = []
    import json
    for link in links:
        metadata = link.get("metadata", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        result.append(MediaLinkWithFileResponse(
            id=link["id"],
            media_id=link["media_id"],
            entity_type=link["entity_type"],
            entity_id=link["entity_id"],
            field_name=link.get("field_name"),
            created_at=link["created_at"],
            original_filename=link["original_filename"],
            mime_type=link["mime_type"],
            size_bytes=link["size_bytes"],
            media_category=link["media_category"],
            status=link["status"],
            metadata=metadata,
            storage_path=link["storage_path"],
            bucket_name=link["bucket_name"],
        ))

    return result


@router.get("/entity/{entity_type}/{entity_id}/content", response_model=EntityContentResponse)
async def get_entity_content(
    entity_type: str,
    entity_id: str,
):
    links = await link_queries.get_links_for_entity(entity_type, entity_id)

    items = []
    for link in links:
        metadata = link.get("metadata", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        text = None
        content_type = None

        ocr = metadata.get("ocr", {})
        if ocr and ocr.get("text"):
            text = ocr["text"]
            content_type = "ocr"

        transcription = metadata.get("transcription", {})
        if transcription and transcription.get("text"):
            text = transcription["text"]
            content_type = "transcription"

        doc_parse = metadata.get("document_parse", {})
        if doc_parse and doc_parse.get("markdown"):
            text = doc_parse["markdown"]
            content_type = "document_parse"

        if text:
            items.append(ContentItem(
                media_id=link["media_id"],
                original_filename=link["original_filename"],
                mime_type=link["mime_type"],
                content_type=content_type,
                text=text,
            ))

    return EntityContentResponse(
        entity_type=entity_type,
        entity_id=entity_id,
        items=items,
    )


@router.post("/internal/batch-process", response_model=BatchProcessResponse)
async def batch_process_files(body: BatchProcessRequest):
    results = []
    for media_id in body.media_ids:
        media = await media_queries.get_media_file(media_id)
        if not media:
            logger.warning("media %s not found, skipping", media_id)
            continue

        metadata = media.get("metadata", {})
        if isinstance(metadata, str):
            import json
            metadata = json.loads(metadata)

        text = None
        content_type = None

        ocr = metadata.get("ocr", {})
        if ocr and ocr.get("text"):
            text = ocr["text"]
            content_type = "ocr"

        transcription = metadata.get("transcription", {})
        if not text and transcription and transcription.get("text"):
            text = transcription["text"]
            content_type = "transcription"

        doc_parse = metadata.get("document_parse", {})
        if not text and doc_parse and doc_parse.get("markdown"):
            text = doc_parse["markdown"]
            content_type = "document_parse"

        if not text:
            file_data = await storage.download_file(
                media["storage_path"], media["bucket_name"]
            )
            if file_data:
                category = media["media_category"]
                result_data = None
                if category == "image":
                    result_data = await vision.ocr_handwriting(file_data)
                    text = result_data.get("text", "")
                    content_type = "ocr"
                elif category == "audio":
                    result_data = await speech.transcribe_audio(
                        file_data, mime_type=media["mime_type"]
                    )
                    text = result_data.get("text", "")
                    content_type = "transcription"
                elif category == "video":
                    result_data = await speech.transcribe_audio(
                        file_data, mime_type=media["mime_type"]
                    )
                    text = result_data.get("text", "")
                    content_type = "transcription"
                elif category == "document":
                    result_data = await document_parser.parse_document_to_markdown(
                        file_data,
                        media["original_filename"],
                        media["mime_type"],
                    )
                    text = result_data.get("markdown", "")
                    content_type = "document_parse"

                if text and result_data:
                    update_key = {
                        "ocr": "ocr",
                        "transcription": "transcription",
                        "document_parse": "document_parse",
                    }.get(content_type)
                    if update_key:
                        await media_queries.update_media_status(
                            media_id, "completed", {update_key: result_data}
                        )

        if text:
            results.append(BatchProcessItem(
                media_id=media_id,
                text=text,
                content_type=content_type or "unknown",
                mime_type=media["mime_type"],
                original_filename=media["original_filename"],
            ))

    return BatchProcessResponse(results=results)


@router.get("/{media_id}/file")
async def stream_file(
    media_id: str,
    user_id: str = Depends(get_user_id),
):
    media = await media_queries.get_media_file(media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found.")
    if media["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied.")

    file_data = await storage.download_file(media["storage_path"], media["bucket_name"])
    if not file_data:
        raise HTTPException(status_code=500, detail="Failed to read file.")

    from fastapi.responses import Response
    return Response(
        content=file_data,
        media_type=media["mime_type"],
        headers={
            "Content-Disposition": f'inline; filename="{media["original_filename"]}"',
            "Content-Length": str(media["size_bytes"]),
        },
    )
