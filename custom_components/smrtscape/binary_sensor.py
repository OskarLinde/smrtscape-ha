from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import SmrtScapeCoordinatorEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities = []
    for block in coordinator.data["locations"]:
        location = block["location"]
        location_id = location["Id"]
        entities.append(SmrtScapeGatewayOnlineBinarySensor(coordinator, entry, location_id))

    async_add_entities(entities)


class SmrtScapeGatewayOnlineBinarySensor(SmrtScapeCoordinatorEntity, BinarySensorEntity):
    def __init__(self, coordinator, config_entry, location_id: int) -> None:
        super().__init__(coordinator, config_entry, location_id)
        self._attr_has_entity_name = True
        self._attr_name = "gateway online"
        self._attr_unique_id = f"{self.location_id}_gateway_online"

    @property
    def is_on(self) -> bool:
        scenes = self.location_block.get("scenes", [])
        for scene in scenes:
            status = scene.get("status", {})
            if "IsGatewayOnline" in status:
                return bool(status["IsGatewayOnline"])
        return False

    @property
    def extra_state_attributes(self) -> dict:
        connected_device = self.location_block["location"].get("ConnectedDevice") or {}
        return {
            "gateway_name": connected_device.get("Name"),
            "gateway_description": connected_device.get("Description"),
            "firmware_version": connected_device.get("FirmwareVersion"),
            "hardware_version": connected_device.get("HardwareVersion"),
            "last_updated": connected_device.get("WhenLastUpdated"),
            "last_known_communication": connected_device.get("WhenLastKnownCommunication"),
        }
