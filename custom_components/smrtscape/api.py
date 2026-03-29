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
            if self._token:
                return

            payload = {
                "Email": self.username,
                "Password": self.password,
                "RememberMe": False,
            }

            data = await self._request(
                "post",
                "/api/v1/auth/login",
                json=payload,
                authenticated=False,
            )

            token = data.get("Token") or data.get("token")
            if not token:
                raise SmrtScapeApiError("Login succeeded but no token was returned")

            self._token = token
            self._user = data

    async def async_get_state(self) -> dict[str, Any]:
        await self.async_login()

        user = self._user or {}
        accounts = user.get("AccountsAdministered") or []
        if not accounts:
            raise SmrtScapeApiError("No administered accounts found")

        account_id = accounts[0]["Id"]
        account_detail = await self._request("get", f"/api/v1/accounts/{account_id}")
        locations = account_detail.get("_locations") or account_detail.get("Locations") or []

        result_locations: list[dict[str, Any]] = []
        for location in locations:
            location_id = location["Id"]
            location_detail = await self._request("get", f"/api/v1/locations/{location_id}")
            scenes = await self._request("get", f"/api/v1/scenes/location/{location_id}")
            scene_statuses = await self._request("get", f"/api/v1/scenes/status/location/{location_id}")
            schedule_summary = await self._request("get", f"/api/v1/scenes/schedulesummary/location/{location_id}")

            status_map = {item["SceneId"]: item for item in scene_statuses}
            summary_map = {item["Id"]: item for item in schedule_summary}

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
        await self._request(
            "put",
            f"/api/v1/scenes/{scene_id}/force",
            params={"action": action, "duration": duration},
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool = True,
        **kwargs: Any,
    ) -> Any:
        headers = kwargs.pop("headers", {})
        headers.setdefault("Accept", "application/json, text/plain, */*")

        if authenticated:
            if not self._token:
                raise SmrtScapeApiError("Client is not authenticated")
            headers["Authorization"] = f"Bearer {self._token}"

        url = f"{self.base_url}{path}"
        async with self.session.request(method.upper(), url, headers=headers, **kwargs) as resp:
            if resp.status == 401 and authenticated:
                self._token = None
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
