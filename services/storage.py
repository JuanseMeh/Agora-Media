from __future__ import annotations

import hashlib
import logging
import os
from io import BytesIO
from typing import BinaryIO
from uuid import uuid4

from config.settings import settings

logger = logging.getLogger(__name__)


_storage_client = None


def _get_client():
    global _storage_client
    if _storage_client is not None:
        return _storage_client
    try:
        from google.cloud import storage
        if settings.google_application_credentials:
            _storage_client = storage.Client.from_service_account_json(
                settings.google_application_credentials
            )
        else:
            _storage_client = storage.Client()
        return _storage_client
    except Exception as e:
        logger.warning("GCS client not available, using local fallback: %s", e)
        return None


def init_storage():
    _get_client()
    logger.info("Storage client initialized (bucket=%s)", settings.gcs_bucket_name)


def close_storage():
    global _storage_client
    _storage_client = None


def _get_bucket():
    client = _get_client()
    if client is None:
        return None
    try:
        return client.bucket(settings.gcs_bucket_name)
    except Exception as e:
        logger.error("Failed to get bucket: %s", e)
        return None


def _generate_storage_path(user_id: str, original_filename: str, media_category: str) -> str:
    ext = os.path.splitext(original_filename)[1]
    file_id = uuid4().hex
    return f"{media_category}/{user_id}/{file_id}{ext}"


def _compute_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def upload_file(
    data: bytes,
    user_id: str,
    original_filename: str,
    mime_type: str,
    media_category: str,
) -> dict:
    storage_path = _generate_storage_path(user_id, original_filename, media_category)
    content_hash = _compute_hash(data)

    bucket = _get_bucket()
    if bucket is not None:
        try:
            blob = bucket.blob(storage_path)
            blob.upload_from_string(
                data,
                content_type=mime_type,
            )
            logger.info(
                "Uploaded to GCS: %s (%d bytes)", storage_path, len(data)
            )
        except Exception as e:
            logger.error("GCS upload failed: %s", e)
            raise RuntimeError(f"Failed to upload to GCS: {e}")
    else:
        local_dir = f"/tmp/media/{storage_path}"
        os.makedirs(os.path.dirname(local_dir), exist_ok=True)
        with open(local_dir, "wb") as f:
            f.write(data)
        logger.info("Stored locally: %s (%d bytes)", local_dir, len(data))

    return {
        "storage_path": storage_path,
        "bucket_name": settings.gcs_bucket_name,
        "content_hash": content_hash,
        "size_bytes": len(data),
    }


async def get_signed_url(storage_path: str, bucket_name: str | None = None) -> str | None:
    bucket = _get_bucket()
    if bucket is None:
        local_path = f"/tmp/media/{storage_path}"
        if os.path.exists(local_path):
            return f"file://{local_path}"
        return None

    try:
        blob = bucket.blob(storage_path)
        url = blob.generate_signed_url(
            expiration=settings.signed_url_expiry_seconds,
            method="GET",
        )
        return url
    except Exception as e:
        logger.error("Failed to generate signed URL: %s", e)
        return None


async def download_file(storage_path: str, bucket_name: str | None = None) -> bytes | None:
    bucket = _get_bucket()
    if bucket is None:
        local_path = f"/tmp/media/{storage_path}"
        if os.path.exists(local_path):
            with open(local_path, "rb") as f:
                return f.read()
        return None

    try:
        blob = bucket.blob(storage_path)
        return blob.download_as_bytes()
    except Exception as e:
        logger.error("Failed to download file: %s", e)
        return None


async def delete_file(storage_path: str, bucket_name: str | None = None) -> bool:
    bucket = _get_bucket()
    if bucket is None:
        local_path = f"/tmp/media/{storage_path}"
        if os.path.exists(local_path):
            os.remove(local_path)
            return True
        return False

    try:
        blob = bucket.blob(storage_path)
        blob.delete()
        return True
    except Exception as e:
        logger.error("Failed to delete file: %s", e)
        return False
