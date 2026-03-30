from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import asyncio
import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)


class SmrtScapeApiError(Exception):
    """Raised when the SMRTScape API returns an error."""


@dataclass
class SmrtScapeApiClient:
    session: aiohttp.ClientSession
    base_url: str
    username: str
    password: str

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self._token: str | None = None
        self._user: dict[str, Any] | None = None
        self._lock = asyncio.Lock()

    async def async_login(self) -> None:
        async with self._lock:
            if self._token and self._user:
                return

            encoded_email = self.username.replace("+", "%2b")
            headers = {"Authorization": f"Basic ?email={encoded_email}&password={self.password}"}
            user = await self._request(
                "get",
                "/api/v1/users?detailed=true",
                authenticated=False,
                headers=headers,
            )
            token = user.get("Token") or user.get("token")
            if not token:
                raise SmrtScapeApiError("Login succeeded but no token was returned")

            self._token = token
            self._user = user

    async def async_get_state(self) -> dict[str, Any]:
        try:
            return await self._async_get_state_once()
        except SmrtScapeApiError as err:
            if "expired" not in str(err).lower() and "401" not in str(err):
                raise
            _LOGGER.debug("Token expired while fetching state, retrying login")
            self._token = None
            self._user = None
            await self.async_login()
            return await self._async_get_state_once()

    async def _async_get_state_once(self) -> dict[str, Any]:
        await self.async_login()

        user = self._user or {}
        accounts = user.get("AccountsAdministered") or []
        if not accounts:
            raise SmrtScapeApiError("No administered accounts found")

        account_id = accounts[0]["Id"]
        account_detail = await self._request(
            "get", f"/api/v1/accounts/{account_id}?detailed=true", auth_mode="basic_id_token"
        )
        locations = account_detail.get("_locations") or account_detail.get("Locations") or []

        result_locations: list[dict[str, Any]] = []
        for location in locations:
            location_id = location["Id"]
            location_detail = await self._request(
                "get",
                f"/api/v1/locations/{location_id}?detailed=true&includeSceneScheduleSummary=true",
                auth_mode="basic_id_token",
            )
            scenes_response = await self._request(
                "get", f"/api/v1/scenes/byLocation/{location_id}", auth_mode="basic_id_token"
            )
            scene_statuses = await self._request(
                "get", f"/api/v1/scenes/status/byLocation/{location_id}", auth_mode="basic_id_token"
            )

            if isinstance(scenes_response, dict):
                scenes = scenes_response.get("Scenes") or scenes_response.get("DeviceGroups") or []
                schedule_summary = (
                    scenes_response.get("SceneScheduleSummaryList")
                    or location_detail.get("SceneScheduleSummaryList")
                    or []
                )
            elif isinstance(scenes_response, list):
                scenes = scenes_response
                schedule_summary = location_detail.get("SceneScheduleSummaryList") or []
            else:
                raise SmrtScapeApiError(
                    f"Unexpected scenes response type for location {location_id}: {type(scenes_response).__name__}"
                )

            if not isinstance(scene_statuses, list):
                raise SmrtScapeApiError(
                    f"Unexpected scene status response type for location {location_id}: {type(scene_statuses).__name__}"
                )

            status_map = {item["SceneId"]: item for item in scene_statuses if isinstance(item, dict) and "SceneId" in item}
            summary_map = {item["Id"]: item for item in schedule_summary if isinstance(item, dict) and "Id" in item}

            merged_scenes = []
            for scene in scenes:
                scene_id = scene["Id"]
                merged_scenes.append(
                    {
                        **scene,
                        "status": status_map.get(scene_id, {}),
                        "schedule_summary": summary_map.get(scene_id, {}),
                    }
                )

            result_locations.append(
                {
                    "location": location_detail,
                    "scenes": merged_scenes,
                }
            )

        return {
            "user": user,
            "locations": result_locations,
        }

    async def async_set_scene(self, scene_id: int, turn_on: bool, duration: int = 0) -> None:
        await self.async_login()
        action = "on" if turn_on else "off"
        try:
            await self._request(
                "put",
                f"/api/v1/scenes/{scene_id}/force",
                params={"action": action, "duration": duration},
                auth_mode="basic_id_token",
            )
        except SmrtScapeApiError as err:
            if "expired" not in str(err).lower() and "401" not in str(err):
                raise
            _LOGGER.debug("Token expired while setting scene %s, retrying login", scene_id)
            self._token = None
            self._user = None
            await self.async_login()
            await self._request(
                "put",
                f"/api/v1/scenes/{scene_id}/force",
                params={"action": action, "duration": duration},
                auth_mode="basic_id_token",
            )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool = True,
        auth_mode: str = "session",
        **kwargs: Any,
    ) -> Any:
        headers = kwargs.pop("headers", {})
        headers.setdefault("Accept", "application/json, text/plain, */*")
        headers.setdefault("X-Requested-With", "XMLHttpRequest")

        if authenticated:
            if not self._token or not self._user:
                raise SmrtScapeApiError("Client is not authenticated")
            if auth_mode == "basic_id_token":
                user_id = self._user.get("Id")
                headers["Authorization"] = f"Basic ?id={user_id}&token={self._token}"
            else:
                headers["Authorization"] = self._token
        elif auth_mode == "user_token":
            user_id = self._user.get("Id") if self._user else None
            token = self._token or (self._user or {}).get("Token")
            if not user_id or not token:
                raise SmrtScapeApiError("Client is not authenticated")
            headers["Authorization"] = f"Basic ?id={user_id}&token={token}"

        url = f"{self.base_url}{path}"
        async with self.session.request(method.upper(), url, headers=headers, **kwargs) as resp:
            if resp.status == 401 and authenticated:
                self._token = None
                self._user = None
                raise SmrtScapeApiError("Authentication failed or expired")

            if resp.status >= 400:
                text = await resp.text()
                raise SmrtScapeApiError(f"HTTP {resp.status} for {path}: {text[:500]}")

            content_type = resp.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return await resp.json()

            text = await resp.text()
            if not text:
                return None

            return text
