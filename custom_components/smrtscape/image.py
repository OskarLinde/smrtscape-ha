from __future__ import annotations

from datetime import datetime
from urllib.request import Request, urlopen

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import SmrtScapeCoordinatorEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities = []
    for block in coordinator.data["locations"]:
        location_id = block["location"]["Id"]
        for scene in block["scenes"]:
            if _scene_image_url(scene):
                entities.append(SmrtScapeSceneImage(hass, coordinator, entry, location_id, scene))

    async_add_entities(entities)


def _scene_image_url(scene: dict) -> str | None:
    image_asset = scene.get("ImageAsset") or {}
    items = image_asset.get("ImageAssetItems") or []
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict) and item.get("Uri"):
            return item["Uri"]
    return None


def _scene_image_updated(scene: dict) -> datetime | None:
    raw = scene.get("WhenImageLastUpdated") or scene.get("WhenImageCreated")
    if not raw or not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


class SmrtScapeSceneImage(SmrtScapeCoordinatorEntity, ImageEntity):
    def __init__(self, hass: HomeAssistant, coordinator, config_entry, location_id: int, scene: dict) -> None:
        ImageEntity.__init__(self, hass)
        SmrtScapeCoordinatorEntity.__init__(self, coordinator, config_entry, location_id, scene)
        self._attr_has_entity_name = True
        self._attr_name = f"{scene['Name'].strip()} image"
        self._attr_unique_id = f"{self.location_id}_{self.scene_id}_image"
        self._attr_content_type = "image/png"
        self._attr_image_last_updated = _scene_image_updated(scene)
        self._cached_bytes: bytes | None = None
        self._cached_cache_key: tuple[str | None, str | None] | None = None

    @property
    def image_url(self) -> str | None:
        return None

    @property
    def image_last_updated(self) -> datetime | None:
        return _scene_image_updated(self.scene_data)

    async def async_image(self) -> bytes | None:
        return await self.hass.async_add_executor_job(self._fetch_image_bytes)

    def _fetch_image_bytes(self) -> bytes | None:
        url = _scene_image_url(self.scene_data)
        updated = _scene_image_updated(self.scene_data)
        cache_key = (url, updated.isoformat() if updated else None)

        if self._cached_cache_key == cache_key and self._cached_bytes is not None:
            return self._cached_bytes

        if not url:
            self._cached_cache_key = None
            self._cached_bytes = None
            return None

        request = Request(url, headers={"User-Agent": "Home Assistant SMRTScape"})
        with urlopen(request, timeout=20) as response:
            content_type = response.headers.get("content-type") or "application/octet-stream"
            data = response.read()

        if content_type == "application/octet-stream":
            lower_url = url.lower()
            if lower_url.endswith(".png"):
                content_type = "image/png"
            elif lower_url.endswith(".jpg") or lower_url.endswith(".jpeg"):
                content_type = "image/jpeg"
            elif lower_url.endswith(".gif"):
                content_type = "image/gif"
            elif lower_url.endswith(".webp"):
                content_type = "image/webp"

        self._attr_content_type = content_type
        self._attr_image_last_updated = updated
        self._cached_cache_key = cache_key
        self._cached_bytes = data
        return data

    @property
    def extra_state_attributes(self) -> dict:
        image_asset = self.scene_data.get("ImageAsset") or {}
        items = image_asset.get("ImageAssetItems") or []
        first = items[0] if items and isinstance(items[0], dict) else {}
        return {
            "image_asset_id": self.scene_data.get("ImageAssetId"),
            "image_id": self.scene_data.get("ImageId"),
            "image_asset_uid": image_asset.get("Uid"),
            "image_name": first.get("Name"),
            "image_width": first.get("Width"),
            "image_height": first.get("Height"),
        }
