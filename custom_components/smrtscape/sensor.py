from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
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
            entities.append(SmrtScapeSceneStatusSensor(coordinator, entry, location_id, scene))
            entities.append(SmrtScapeSceneNextStatusSensor(coordinator, entry, location_id, scene))

    async_add_entities(entities)


class _BaseSceneSensor(SmrtScapeCoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, config_entry, location_id: int, scene: dict, suffix: str) -> None:
        super().__init__(coordinator, config_entry, location_id, scene)
        self._attr_has_entity_name = True
        self._scene_name = scene["Name"].strip()
        self._attr_unique_id = f"{self.location_id}_{self.scene_id}_{suffix}"


class SmrtScapeSceneStatusSensor(_BaseSceneSensor):
    def __init__(self, coordinator, config_entry, location_id: int, scene: dict) -> None:
        super().__init__(coordinator, config_entry, location_id, scene, "status")
        self._attr_name = f"{self._scene_name} status"

    @property
    def native_value(self) -> str | None:
        return self.scene_data.get("status", {}).get("StatusText")


class SmrtScapeSceneNextStatusSensor(_BaseSceneSensor):
    def __init__(self, coordinator, config_entry, location_id: int, scene: dict) -> None:
        super().__init__(coordinator, config_entry, location_id, scene, "next_status")
        self._attr_name = f"{self._scene_name} next status"

    @property
    def native_value(self) -> str | None:
        return self.scene_data.get("status", {}).get("NextStatusText")
