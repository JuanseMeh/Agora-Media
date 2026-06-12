from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class MediaFileResponse(BaseModel):
    id: str
    user_id: str
    original_filename: str
    mime_type: str
    size_bytes: int
    storage_path: str
    bucket_name: str
    content_hash: str | None = None
    media_category: str
    status: str
    metadata: dict[str, Any] = {}
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    created_at: str
    updated_at: str


class MediaLinkResponse(BaseModel):
    id: str
    media_id: str
    entity_type: str
    entity_id: str
    field_name: str | None = None
    created_at: str


class MediaLinkWithFileResponse(MediaLinkResponse):
    original_filename: str
    mime_type: str
    size_bytes: int
    media_category: str
    status: str
    metadata: dict[str, Any] = {}
    storage_path: str
    bucket_name: str


class UploadResponse(BaseModel):
    media: MediaFileResponse
    signed_url: str | None = None


class ProcessingResult(BaseModel):
    media_id: str
    processing_type: str
    status: str
    result: dict[str, Any] = {}


class CreateLinkRequest(BaseModel):
    media_id: str
    entity_type: Literal["submission", "assignment", "user_profile", "workspace"]
    entity_id: str
    field_name: str | None = None


class ErrorResponse(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status: str
    database: str
    storage: str


class ContentItem(BaseModel):
    media_id: str
    original_filename: str
    mime_type: str
    content_type: str
    text: str


class EntityContentResponse(BaseModel):
    entity_type: str
    entity_id: str
    items: list[ContentItem]


class BatchProcessItem(BaseModel):
    media_id: str
    text: str
    content_type: str
    mime_type: str
    original_filename: str


class BatchProcessRequest(BaseModel):
    media_ids: list[str]


class BatchProcessResponse(BaseModel):
    results: list[BatchProcessItem]
