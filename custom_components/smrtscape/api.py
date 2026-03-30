from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import asyncio
import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)


def _summarize_payload(value: Any) -> str:
    if isinstance(value, dict):
        keys = ", ".join(sorted(str(key) for key in value.keys())[:8])
        return f"dict(keys=[{keys}])"
    if isinstance(value, list):
        return f"list(len={len(value)})"
    return type(value).__name__


def _ensure_dict(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SmrtScapeApiError(f"Unexpected {context} response type: {type(value).__name__}")
    return value


def _ensure_list(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise SmrtScapeApiError(f"Unexpected {context} response type: {type(value).__name__}")
    return value


class SmrtScapeApiError(Exception):
    """Raised when the SMRTScape API returns an error."""


class SmrtScapeGatewayOfflineError(SmrtScapeApiError):
    """Raised when the SMRTScape gateway is offline."""


class SmrtScapeAuthenticationError(SmrtScapeApiError):
    """Raised when authentication fails."""


class SmrtScapeRequestError(SmrtScapeApiError):
    """Raised for sanitized upstream request failures."""


@dataclass
class SmrtScapeApiClient:
    session: aiohttp.ClientSession
    base_url: str
    username: str
    password: str

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self._token: str | None = None
        self._user_id: int | None = None
        self._account_ids: list[int] = []
        self._lock = asyncio.Lock()

    async def async_login(self) -> None:
        async with self._lock:
            if self._token and self._user_id and self._account_ids:
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
            user_id = user.get("Id")
            accounts = user.get("AccountsAdministered") or []
            account_ids = [account["Id"] for account in accounts if isinstance(account, dict) and "Id" in account]

            if not token or not user_id:
                raise SmrtScapeApiError("Login succeeded but required identity fields were missing")
            if not account_ids:
                raise SmrtScapeApiError("No administered accounts found")

            self._token = token
            self._user_id = int(user_id)
            self._account_ids = [int(account_id) for account_id in account_ids]

    async def async_get_state(self) -> dict[str, Any]:
        try:
            return await self._async_get_state_once()
        except SmrtScapeApiError as err:
            if "expired" not in str(err).lower() and "401" not in str(err):
                raise
            _LOGGER.debug("Token expired while fetching state, retrying login")
            self._token = None
            self._user_id = None
            self._account_ids = []
            await self.async_login()
            return await self._async_get_state_once()

    async def _async_get_state_once(self) -> dict[str, Any]:
        await self.async_login()

        if not self._account_ids:
            raise SmrtScapeApiError("No administered accounts found")

        account_id = self._account_ids[0]
        account_detail = _ensure_dict(
            await self._request(
                "get", f"/api/v1/accounts/{account_id}?detailed=true", auth_mode="basic_id_token"
            ),
            "account detail",
        )

        locations = _ensure_list(
            account_detail.get("_locations") or account_detail.get("Locations") or [],
            f"locations payload for account {account_id}",
        )

        result_locations: list[dict[str, Any]] = []
        for location in locations:
            if not isinstance(location, dict) or "Id" not in location:
                _LOGGER.warning(
                    "Skipping malformed location payload: %s",
                    _summarize_payload(location),
                )
                continue

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

            location_detail = _ensure_dict(location_detail, f"location detail for location {location_id}")

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

            scenes = _ensure_list(scenes, f"scenes list for location {location_id}")

            if not isinstance(schedule_summary, list):
                _LOGGER.warning(
                    "Unexpected schedule summary type for location %s: %s",
                    location_id,
                    type(schedule_summary).__name__,
                )
                schedule_summary = []

            scene_statuses = _ensure_list(scene_statuses, f"scene status list for location {location_id}")

            status_map = {item["SceneId"]: item for item in scene_statuses if isinstance(item, dict) and "SceneId" in item}
            summary_map = {item["Id"]: item for item in schedule_summary if isinstance(item, dict) and "Id" in item}

            merged_scenes = []
            for scene in scenes:
                if not isinstance(scene, dict) or "Id" not in scene:
                    _LOGGER.warning(
                        "Skipping malformed scene payload for location %s: %s",
                        location_id,
                        _summarize_payload(scene),
                    )
                    continue
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
            "user": {
                "Id": self._user_id,
                "AccountsAdministered": [{"Id": account_id} for account_id in self._account_ids],
            },
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
            self._user_id = None
            self._account_ids = []
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
            if not self._token or not self._user_id:
                raise SmrtScapeApiError("Client is not authenticated")
            if auth_mode == "basic_id_token":
                headers["Authorization"] = f"Basic ?id={self._user_id}&token={self._token}"
            else:
                headers["Authorization"] = self._token
        elif auth_mode == "user_token":
            if not self._user_id or not self._token:
                raise SmrtScapeApiError("Client is not authenticated")
            headers["Authorization"] = f"Basic ?id={self._user_id}&token={self._token}"

        url = f"{self.base_url}{path}"
        async with self.session.request(method.upper(), url, headers=headers, **kwargs) as resp:
            if resp.status == 401 and authenticated:
                self._token = None
                self._user_id = None
                self._account_ids = []
                raise SmrtScapeAuthenticationError("Authentication failed or expired")

            if resp.status >= 400:
                text = await resp.text()
                lowered = text.lower()
                if resp.status == 401:
                    raise SmrtScapeAuthenticationError("Authentication failed")
                if resp.status == 403:
                    raise SmrtScapeRequestError("Access denied by SMRTScape")
                if resp.status == 404:
                    raise SmrtScapeRequestError("SMRTScape endpoint not found")
                if resp.status == 429:
                    raise SmrtScapeRequestError("SMRTScape rate limited the request")
                if resp.status == 500 and "gateway is not communicating" in lowered:
                    raise SmrtScapeGatewayOfflineError("Gateway offline")
                _LOGGER.debug("SMRTScape API error %s on %s: %s", resp.status, path, text[:300])
                if 400 <= resp.status < 500:
                    raise SmrtScapeRequestError(f"SMRTScape rejected the request ({resp.status})")
                raise SmrtScapeRequestError(f"SMRTScape server error ({resp.status})")

            content_type = resp.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return await resp.json()

            text = await resp.text()
            if not text:
                return None

            return text
