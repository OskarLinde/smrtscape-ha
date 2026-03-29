from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class SmrtScapeCoordinatorEntity(CoordinatorEntity):
    def __init__(self, coordinator, config_entry, location_id: int, scene: dict | None = None) -> None:
        super().__init__(coordinator)
        self.config_entry = config_entry
        self.location_id = location_id
        self.scene_id = scene["Id"] if scene else None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"location_{self.location_id}")},
            name=self.location_name,
            manufacturer="Toro",
            model="SMRTScape",
            configuration_url="https://smrtscape.com",
        )

    @property
    def location_block(self) -> dict:
        for block in self.coordinator.data["locations"]:
            if block["location"]["Id"] == self.location_id:
                return block
        raise KeyError(self.location_id)

    @property
    def location_name(self) -> str:
        return self.location_block["location"]["Name"]

    @property
    def scene_data(self) -> dict:
        for scene in self.location_block["scenes"]:
            if scene["Id"] == self.scene_id:
                return scene
        raise KeyError(self.scene_id)
