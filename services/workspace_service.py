from __future__ import annotations

import logging

from config.settings import settings
from db.queries import media_links as link_queries
from services.http_client import get_workspace_client, raise_for_service_error

logger = logging.getLogger(__name__)


async def check_workspace_member(workspace_id: int, user_id: str) -> bool:
    client = get_workspace_client()
    try:
        response = await client.get(
            f"/workspaces/member/workspace/{workspace_id}",
            headers={"X-User-Id": user_id},
        )
        if not response.is_success:
            return False
        members = response.json()
        return any(str(m.get("userId")) == user_id for m in members)
    except Exception as e:
        logger.warning("Failed to check workspace membership: %s", e)
        return False


async def check_assignment_access(assignment_id: int, user_id: str) -> bool:
    client = get_workspace_client()
    try:
        response = await client.get(
            f"/workspaces/assignments/{assignment_id}",
            headers={"X-User-Id": user_id},
        )
        if not response.is_success:
            return False
        assignment = response.json()
        workspace_id = assignment.get("workspaceId")
        if not workspace_id:
            return False
        return await check_workspace_member(workspace_id, user_id)
    except Exception as e:
        logger.warning("Failed to check assignment access: %s", e)
        return False


async def check_submission_access(submission_id: int, user_id: str) -> bool:
    client = get_workspace_client()
    try:
        response = await client.get(
            f"/workspaces/submission/{submission_id}",
            headers={"X-User-Id": user_id},
        )
        if not response.is_success:
            return False
        submission = response.json()
        if str(submission.get("userId")) == user_id:
            return True
        assignment_id = submission.get("assignmentId")
        if assignment_id:
            return await check_assignment_access(assignment_id, user_id)
        return False
    except Exception as e:
        logger.warning("Failed to check submission access: %s", e)
        return False


async def get_user_workspace_ids(user_id: str) -> set[int]:
    client = get_workspace_client()
    try:
        response = await client.get(
            "/workspaces/member/user",
            headers={"X-User-Id": user_id},
        )
        if not response.is_success:
            return set()
        memberships = response.json()
        return {m.get("workspaceId") for m in memberships if m.get("workspaceId")}
    except Exception as e:
        logger.warning("Failed to get user workspaces: %s", e)
        return set()


async def check_media_access(media_id: str, user_id: str, owner_id: str | None = None) -> bool:
    links = await link_queries.get_links_for_media(media_id)
    for link in links:
        entity_type = link.get("entity_type")
        entity_id = link.get("entity_id")
        if not entity_type or not entity_id:
            continue
        if entity_type == "assignment":
            if await check_assignment_access(int(entity_id), user_id):
                return True
        elif entity_type == "submission":
            if await check_submission_access(int(entity_id), user_id):
                return True

    if owner_id and owner_id != user_id:
        user_workspaces = await get_user_workspace_ids(user_id)
        owner_workspaces = await get_user_workspace_ids(owner_id)
        if user_workspaces & owner_workspaces:
            return True

    return False


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
