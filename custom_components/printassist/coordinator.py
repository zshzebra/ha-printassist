"""Data coordinator for PrintAssist."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .scheduler import PrintScheduler, ScheduledJob

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

    def _estimate_active_job_end(self) -> datetime | None:
        active_job = self._store.get_active_job()
        if not active_job or not active_job.started_at:
            return None

        plate = self._store.get_plate(active_job.plate_id)
        if not plate:
            return None

        started = datetime.fromisoformat(active_job.started_at)
        return started + timedelta(seconds=plate.estimated_duration_seconds)

    def _run_scheduler(self) -> list[ScheduledJob]:
        queued_jobs = self._store.get_queued_jobs()
        plates = self._store.get_plates()
        plates_by_id = {p.id: p for p in plates}
        unavailability = self._store.get_unavailability_windows()
        active_job_end = self._estimate_active_job_end()

        scheduler = PrintScheduler(
            queued_jobs=queued_jobs,
            plates_by_id=plates_by_id,
            unavailability_windows=unavailability,
            active_job_end=active_job_end,
        )

        return scheduler.calculate_schedule()

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

        scheduled = self._run_scheduler()
        schedule_data = []
        for sj in scheduled:
            schedule_data.append({
                "job_id": sj.job_id,
                "plate_id": sj.plate_id,
                "plate_name": sj.plate_name,
                "plate_number": sj.plate_number,
                "source_filename": sj.source_filename,
                "scheduled_start": sj.scheduled_start.isoformat(),
                "scheduled_end": sj.scheduled_end.isoformat(),
                "estimated_duration_seconds": sj.estimated_duration_seconds,
                "spans_unavailability": sj.spans_unavailability,
                "thumbnail_path": sj.thumbnail_path,
            })

        next_scheduled = scheduled[0] if scheduled else None

        return {
            "projects": self._store.get_projects(),
            "plates": self._store.get_plates(),
            "queued_jobs": [j for j, _ in sorted_jobs],
            "active_job": active_job,
            "active_plate": active_plate,
            "queue_count": len(queued_jobs),
            "next_job": sorted_jobs[0][0] if sorted_jobs else None,
            "next_plate": sorted_jobs[0][1] if sorted_jobs else None,
            "next_scheduled": next_scheduled,
            "schedule": schedule_data,
            "unavailability_windows": self._store.get_unavailability_windows(),
        }
