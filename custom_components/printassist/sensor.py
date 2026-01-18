"""Sensors for PrintAssist."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
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
        PrintAssistTimeToChangeSensor(coordinator),
        PrintAssistScheduleSensor(coordinator),
        PrintAssistPartsPrintedSensor(coordinator),
        PrintAssistTotalPartsSensor(coordinator),
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
        next_scheduled = self.coordinator.data.get("next_scheduled")
        return next_scheduled.plate_name if next_scheduled else None

    @property
    def entity_picture(self) -> str | None:
        if not self.coordinator.data:
            return None
        next_scheduled = self.coordinator.data.get("next_scheduled")
        if next_scheduled and next_scheduled.thumbnail_path:
            return next_scheduled.thumbnail_path
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        next_scheduled = self.coordinator.data.get("next_scheduled")
        if not next_scheduled:
            return {}
        return {
            "job_id": next_scheduled.job_id,
            "plate_id": next_scheduled.plate_id,
            "plate_number": next_scheduled.plate_number,
            "source_filename": next_scheduled.source_filename,
            "estimated_duration_seconds": next_scheduled.estimated_duration_seconds,
            "scheduled_start": next_scheduled.scheduled_start.isoformat(),
            "scheduled_end": next_scheduled.scheduled_end.isoformat(),
            "spans_unavailability": next_scheduled.spans_unavailability,
            "thumbnail": next_scheduled.thumbnail_path,
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
    def entity_picture(self) -> str | None:
        if not self.coordinator.data:
            return None
        active_plate = self.coordinator.data.get("active_plate")
        if active_plate and active_plate.thumbnail_path:
            return active_plate.thumbnail_path
        return None

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
            "thumbnail": active_plate.thumbnail_path,
        }


class PrintAssistTimeToChangeSensor(PrintAssistSensorBase):
    def __init__(self, coordinator: PrintAssistCoordinator) -> None:
        super().__init__(coordinator, "time_to_next_change", "Time to Next Change")
        self._attr_icon = "mdi:timer-outline"
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_native_unit_of_measurement = UnitOfTime.MINUTES

    @property
    def native_value(self) -> int | None:
        end_time = self.coordinator.get_active_job_end_time()
        if not end_time:
            return None
        now = datetime.now(timezone.utc)
        if end_time <= now:
            return 0
        return int((end_time - now).total_seconds() / 60)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        end_time = self.coordinator.get_active_job_end_time()
        if not end_time:
            return {}
        return {"end_time": end_time.isoformat()}


class PrintAssistScheduleSensor(PrintAssistSensorBase):
    def __init__(self, coordinator: PrintAssistCoordinator) -> None:
        super().__init__(coordinator, "schedule", "Schedule")
        self._attr_icon = "mdi:calendar-clock"
        self._attr_native_unit_of_measurement = "jobs"

    @property
    def native_value(self) -> int:
        if not self.coordinator.data:
            return 0
        return len(self.coordinator.data.get("schedule", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        return {"jobs": self.coordinator.data.get("schedule", [])}


class PrintAssistPartsPrintedSensor(PrintAssistSensorBase):
    def __init__(self, coordinator: PrintAssistCoordinator) -> None:
        super().__init__(coordinator, "parts_printed", "Parts Printed")
        self._attr_icon = "mdi:check-circle-outline"
        self._attr_native_unit_of_measurement = "parts"

    @property
    def native_value(self) -> int:
        if not self.coordinator.data:
            return 0
        return self.coordinator.data.get("parts_printed", 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        return {"by_project": self.coordinator.data.get("progress_by_project", [])}


class PrintAssistTotalPartsSensor(PrintAssistSensorBase):
    def __init__(self, coordinator: PrintAssistCoordinator) -> None:
        super().__init__(coordinator, "total_parts", "Total Parts")
        self._attr_icon = "mdi:cube-outline"
        self._attr_native_unit_of_measurement = "parts"

    @property
    def native_value(self) -> int:
        if not self.coordinator.data:
            return 0
        return self.coordinator.data.get("total_parts", 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        return {"by_project": self.coordinator.data.get("progress_by_project", [])}
