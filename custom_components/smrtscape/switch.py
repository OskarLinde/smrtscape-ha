from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_LOCATION_ID, ATTR_SCENE_ID, DOMAIN
from .entity import SmrtScapeCoordinatorEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities = []
    for block in coordinator.data["locations"]:
        location_id = block["location"]["Id"]
        for scene in block["scenes"]:
            entities.append(SmrtScapeSceneSwitch(coordinator, entry, location_id, scene))

    async_add_entities(entities)


class SmrtScapeSceneSwitch(SmrtScapeCoordinatorEntity, SwitchEntity):
    def __init__(self, coordinator, config_entry, location_id: int, scene: dict) -> None:
        super().__init__(coordinator, config_entry, location_id, scene)
        self._attr_has_entity_name = True
        self._attr_name = scene["Name"].strip()
        self._attr_unique_id = f"{self.location_id}_{self.scene_id}"

    @property
    def is_on(self) -> bool:
        return bool(self.scene_data["status"].get("IsSceneOn"))

    @property
    def extra_state_attributes(self) -> dict:
        status = self.scene_data.get("status", {})
        return {
            ATTR_LOCATION_ID: self.location_id,
            ATTR_SCENE_ID: self.scene_id,
            "description": self.scene_data.get("Description", "").strip(),
            "status_text": status.get("StatusText"),
            "next_status_text": status.get("NextStatusText"),
            "is_forced_on": status.get("IsSceneForcedOn"),
            "is_forced_off": status.get("IsSceneForcedOff"),
            "is_scheduled_on": status.get("IsSceneScheduledOn"),
            "last_gateway_communication": status.get("LastGatewayCommunication"),
            "schedule_summary": self.scene_data.get("schedule_summary", {}).get("Schedule"),
        }

    async def async_turn_on(self, **kwargs) -> None:
        await self.hass.data[DOMAIN][self.config_entry.entry_id]["client"].async_set_scene(self.scene_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self.hass.data[DOMAIN][self.config_entry.entry_id]["client"].async_set_scene(self.scene_id, False)
        await self.coordinator.async_request_refresh()
