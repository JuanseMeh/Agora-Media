from __future__ import annotations

import logging

from config.settings import settings
from services.http_client import get_workspace_client, raise_for_service_error

logger = logging.getLogger(__name__)


async def link_file_to_submission(
    submission_id: int,
    user_id: str,
    file_url: str,
    file_name: str,
    file_type: str,
    file_size: int,
) -> bool:
    client = get_workspace_client()

    try:
        response = await client.get(
            f"/workspaces/submission/{submission_id}",
            headers={"X-User-Id": user_id},
        )
        raise_for_service_error(response, "workspace-service")

        submission = response.json()
        existing_files = submission.get("files", {})
        if isinstance(existing_files, str):
            import json
            existing_files = json.loads(existing_files)

        attachments = existing_files.get("attachments", [])
        attachments.append({
            "url": file_url,
            "name": file_name,
            "type": file_type,
            "size": file_size,
        })
        existing_files["attachments"] = attachments

        update_response = await client.put(
            f"/workspaces/submission/{submission_id}",
            json={
                "content": submission.get("content", {}),
                "files": existing_files,
            },
            headers={"X-User-Id": user_id},
        )
        raise_for_service_error(update_response, "workspace-service")
        logger.info(
            "File linked to submission %s: %s", submission_id, file_name
        )
        return True
    except Exception as e:
        logger.error(
            "Failed to link file to submission %s: %s", submission_id, e
        )
        return False


async def link_file_to_assignment(
    assignment_id: int,
    user_id: str,
    file_url: str,
    file_name: str,
    file_type: str,
) -> bool:
    client = get_workspace_client()

    try:
        response = await client.get(
            f"/workspaces/assignments/{assignment_id}",
            headers={"X-User-Id": user_id},
        )
        raise_for_service_error(response, "workspace-service")

        assignment = response.json()
        settings_data = assignment.get("settings", {})
        if isinstance(settings_data, str):
            import json
            settings_data = json.loads(settings_data)

        media = settings_data.get("contextMedia", [])
        media.append({
            "url": file_url,
            "name": file_name,
            "type": file_type,
        })
        settings_data["contextMedia"] = media

        update_response = await client.put(
            f"/workspaces/assignments/{assignment_id}",
            json={
                "settings": settings_data,
            },
            headers={"X-User-Id": user_id},
        )
        raise_for_service_error(update_response, "workspace-service")
        logger.info(
            "File linked to assignment %s: %s", assignment_id, file_name
        )
        return True
    except Exception as e:
        logger.error(
            "Failed to link file to assignment %s: %s", assignment_id, e
        )
        return False
