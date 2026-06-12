from __future__ import annotations

import logging

import httpx

from config.settings import settings
from services.http_client import get_users_client, raise_for_service_error

logger = logging.getLogger(__name__)


async def update_user_profile(
    user_id: str,
    avatar_url: str,
) -> bool:
    client = get_users_client()

    current_user = await _get_user(user_id)
    if current_user is None:
        logger.warning("User %s not found, skipping avatar update", user_id)
        return False

    profile = current_user.get("profile", {})
    if isinstance(profile, str):
        import json
        profile = json.loads(profile)

    profile["avatarUrl"] = avatar_url

    try:
        response = await client.put(
            f"/users/update-user",
            json={
                "firstName": current_user.get("firstName"),
                "lastName": current_user.get("lastName"),
                "email": current_user.get("email"),
                "profile": profile,
            },
            headers={"X-User-Id": user_id},
        )
        raise_for_service_error(response, "user-service")
        logger.info("Avatar updated for user %s: %s", user_id, avatar_url)
        return True
    except Exception as e:
        logger.error("Failed to update avatar for user %s: %s", user_id, e)
        return False


async def _get_user(user_id: str) -> dict | None:
    client = get_users_client()
    try:
        response = await client.get(
            "/users/get-user",
            headers={"X-User-Id": user_id},
        )
        raise_for_service_error(response, "user-service")
        return response.json()
    except Exception as e:
        logger.error("Failed to get user %s: %s", user_id, e)
        return None
