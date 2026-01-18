"""Sensors for PrintAssist."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PrintAssistCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PrintAssistCoordinator = hass.data[DOMAIN]["coordinator"]

    async_add_entities([
        PrintAssistQueueCountSensor(coordinator),
        PrintAssistNextPrintSensor(coordinator),
        PrintAssistActiveJobSensor(coordinator),
    ])


class PrintAssistSensorBase(CoordinatorEntity[PrintAssistCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: PrintAssistCoordinator, key: str, name: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"printassist_{key}"
        self._attr_name = name


class PrintAssistQueueCountSensor(PrintAssistSensorBase):
    def __init__(self, coordinator: PrintAssistCoordinator) -> None:
        super().__init__(coordinator, "queue_count", "Queue Count")
        self._attr_icon = "mdi:format-list-numbered"
        self._attr_native_unit_of_measurement = "jobs"

    @property
    def native_value(self) -> int:
        if not self.coordinator.data:
            return 0
        return self.coordinator.data.get("queue_count", 0)


class PrintAssistNextPrintSensor(PrintAssistSensorBase):
    def __init__(self, coordinator: PrintAssistCoordinator) -> None:
        super().__init__(coordinator, "next_print", "Next Print")
        self._attr_icon = "mdi:printer-3d-nozzle"

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        next_plate = self.coordinator.data.get("next_plate")
        return next_plate.name if next_plate else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        next_job = self.coordinator.data.get("next_job")
        next_plate = self.coordinator.data.get("next_plate")
        if not next_job or not next_plate:
            return {}
        return {
            "job_id": next_job.id,
            "plate_id": next_plate.id,
            "project_id": next_plate.project_id,
            "estimated_duration_seconds": next_plate.estimated_duration_seconds,
            "thumbnail": next_plate.thumbnail_path,
        }


class PrintAssistActiveJobSensor(PrintAssistSensorBase):
    def __init__(self, coordinator: PrintAssistCoordinator) -> None:
        super().__init__(coordinator, "active_job", "Active Job")
        self._attr_icon = "mdi:printer-3d"

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        active_plate = self.coordinator.data.get("active_plate")
        return active_plate.name if active_plate else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        active_job = self.coordinator.data.get("active_job")
        active_plate = self.coordinator.data.get("active_plate")
        if not active_job or not active_plate:
            return {}
        return {
            "job_id": active_job.id,
            "plate_id": active_plate.id,
            "started_at": active_job.started_at,
            "plate_name": active_plate.name,
            "gcode_path": active_plate.gcode_path,
        }
