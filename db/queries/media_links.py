from __future__ import annotations

import logging
from typing import Any

from db.pool import get_pool

logger = logging.getLogger(__name__)


async def create_media_link(
    media_id: str,
    entity_type: str,
    entity_id: str,
    field_name: str | None = None,
) -> dict[str, Any]:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO media_links (media_id, entity_type, entity_id, field_name)
        VALUES ($1::uuid, $2, $3, $4)
        ON CONFLICT (media_id, entity_type, entity_id, field_name)
        DO UPDATE SET created_at = NOW()
        RETURNING id::text, media_id::text, entity_type, entity_id, field_name, created_at::text
        """,
        media_id,
        entity_type,
        entity_id,
        field_name,
    )
    return dict(row)


async def get_links_for_entity(
    entity_type: str, entity_id: str
) -> list[dict[str, Any]]:
    import json
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT ml.id::text, ml.media_id::text, ml.entity_type, ml.entity_id,
               ml.field_name, ml.created_at::text,
               mf.original_filename, mf.mime_type, mf.size_bytes,
               mf.media_category::text, mf.status::text, mf.metadata,
               mf.storage_path, mf.bucket_name
        FROM media_links ml
        JOIN media_files mf ON mf.id = ml.media_id
        WHERE ml.entity_type = $1 AND ml.entity_id = $2
        ORDER BY ml.created_at DESC
        """,
        entity_type,
        entity_id,
    )
    result = []
    for r in rows:
        row = dict(r)
        if isinstance(row.get("metadata"), str):
            row["metadata"] = json.loads(row["metadata"])
        result.append(row)
    return result


async def get_links_for_media(media_id: str) -> list[dict[str, Any]]:
    pool = get_pool()
    rows = await pool.fetch(
        """
        SELECT id::text, media_id::text, entity_type, entity_id, field_name, created_at::text
        FROM media_links
        WHERE media_id = $1::uuid
        """,
        media_id,
    )
    return [dict(r) for r in rows]


async def get_media_link_by_id(link_id: str) -> dict[str, Any] | None:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        SELECT id::text, media_id::text, entity_type, entity_id, field_name, created_at::text
        FROM media_links
        WHERE id = $1::uuid
        """,
        link_id,
    )
    return dict(row) if row else None


async def delete_media_link(link_id: str) -> bool:
    pool = get_pool()
    result = await pool.execute(
        "DELETE FROM media_links WHERE id = $1::uuid",
        link_id,
    )
    return result != "DELETE 0"


async def delete_links_for_media(media_id: str) -> None:
    pool = get_pool()
    await pool.execute(
        "DELETE FROM media_links WHERE media_id = $1::uuid",
        media_id,
    )
