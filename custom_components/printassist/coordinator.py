"""Data coordinator for PrintAssist."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from .store import PrintAssistStore

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)


class PrintAssistCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, store: PrintAssistStore) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self._store = store

    async def _async_update_data(self) -> dict[str, Any]:
        queued_jobs = self._store.get_queued_jobs()

        sorted_jobs = []
        for job in queued_jobs:
            plate = self._store.get_plate(job.plate_id)
            if plate:
                sorted_jobs.append((job, plate))
        sorted_jobs.sort(key=lambda x: -x[1].priority)

        active_job = self._store.get_active_job()
        active_plate = None
        if active_job:
            active_plate = self._store.get_plate(active_job.plate_id)

        next_job = sorted_jobs[0] if sorted_jobs else None

        return {
            "projects": self._store.get_projects(),
            "plates": self._store.get_plates(),
            "queued_jobs": [j for j, _ in sorted_jobs],
            "active_job": active_job,
            "active_plate": active_plate,
            "queue_count": len(queued_jobs),
            "next_job": next_job[0] if next_job else None,
            "next_plate": next_job[1] if next_job else None,
            "unavailability_windows": self._store.get_unavailability_windows(),
        }
