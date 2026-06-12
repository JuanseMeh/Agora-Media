from __future__ import annotations

import logging
from typing import Any

from db.pool import get_pool

logger = logging.getLogger(__name__)


async def create_media_file(
    user_id: str,
    original_filename: str,
    mime_type: str,
    size_bytes: int,
    storage_path: str,
    bucket_name: str,
    content_hash: str | None,
    media_category: str,
    width: int | None = None,
    height: int | None = None,
) -> dict[str, Any]:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO media_files
            (user_id, original_filename, mime_type, size_bytes,
             storage_path, bucket_name, content_hash, media_category,
             width, height)
        VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8::media_category, $9, $10)
        RETURNING
            id::text, user_id::text, original_filename, mime_type,
            size_bytes, storage_path, bucket_name, content_hash,
            media_category::text, status::text, metadata,
            width, height, duration_seconds,
            created_at::text, updated_at::text
        """,
        user_id,
        original_filename,
        mime_type,
        size_bytes,
        storage_path,
        bucket_name,
        content_hash,
        media_category,
        width,
        height,
    )
    return dict(row)


async def get_media_file(media_id: str) -> dict[str, Any] | None:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        SELECT
            id::text, user_id::text, original_filename, mime_type,
            size_bytes, storage_path, bucket_name, content_hash,
            media_category::text, status::text, metadata,
            width, height, duration_seconds,
            created_at::text, updated_at::text
        FROM media_files
        WHERE id = $1::uuid
        """,
        media_id,
    )
    return dict(row) if row else None


async def update_media_status(
    media_id: str, status: str, metadata: dict[str, Any] | None = None
) -> None:
    pool = get_pool()
    if metadata is not None:
        import json
        await pool.execute(
            """
            UPDATE media_files
            SET status = $2::media_status,
                metadata = metadata || $3::jsonb,
                updated_at = NOW()
            WHERE id = $1::uuid
            """,
            media_id,
            status,
            json.dumps(metadata),
        )
    else:
        await pool.execute(
            """
            UPDATE media_files
            SET status = $2::media_status, updated_at = NOW()
            WHERE id = $1::uuid
            """,
            media_id,
            status,
        )


async def update_media_metadata(
    media_id: str, metadata: dict[str, Any]
) -> None:
    pool = get_pool()
    import json
    await pool.execute(
        """
        UPDATE media_files
        SET metadata = metadata || $2::jsonb, updated_at = NOW()
        WHERE id = $1::uuid
        """,
        media_id,
        json.dumps(metadata),
    )


async def delete_media_file(media_id: str) -> bool:
    pool = get_pool()
    result = await pool.execute(
        "DELETE FROM media_files WHERE id = $1::uuid",
        media_id,
    )
    return result != "DELETE 0"


async def list_user_media(
    user_id: str,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    pool = get_pool()
    if category:
        rows = await pool.fetch(
            """
            SELECT
                id::text, user_id::text, original_filename, mime_type,
                size_bytes, storage_path, bucket_name, content_hash,
                media_category::text, status::text, metadata,
                width, height, duration_seconds,
                created_at::text, updated_at::text
            FROM media_files
            WHERE user_id = $1::uuid AND media_category = $2::media_category
            ORDER BY created_at DESC
            LIMIT $3 OFFSET $4
            """,
            user_id,
            category,
            limit,
            offset,
        )
    else:
        rows = await pool.fetch(
            """
            SELECT
                id::text, user_id::text, original_filename, mime_type,
                size_bytes, storage_path, bucket_name, content_hash,
                media_category::text, status::text, metadata,
                width, height, duration_seconds,
                created_at::text, updated_at::text
            FROM media_files
            WHERE user_id = $1::uuid
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            user_id,
            limit,
            offset,
        )
    return [dict(r) for r in rows]
