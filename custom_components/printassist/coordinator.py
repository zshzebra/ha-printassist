"""Data coordinator for PrintAssist."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .scheduler import PrintScheduler, ScheduledJob, ScheduleResult

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from .store import PrintAssistStore
    from .printer_monitor import BambuPrinterMonitor

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)


class PrintAssistCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(
        self,
        hass: HomeAssistant,
        store: PrintAssistStore,
        printer_monitor: BambuPrinterMonitor | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self._store = store
        self._printer_monitor = printer_monitor
        self._schedule_result: ScheduleResult | None = None
        self._last_input_hash: str | None = None

    def set_printer_monitor(self, monitor: BambuPrinterMonitor) -> None:
        self._printer_monitor = monitor

    def _compute_input_hash(self) -> str:
        queued_jobs = self._store.get_queued_jobs()
        plates = self._store.get_plates()
        unavailability = self._store.get_unavailability_windows()
        active_job = self._store.get_active_job()

        blocking_end = None
        if self._printer_monitor:
            be = self._printer_monitor.get_blocking_end_time()
            if be:
                blocking_end = be.isoformat()

        data = {
            "jobs": [(j.id, j.plate_id, j.status) for j in queued_jobs],
            "plates": [(p.id, p.priority, p.estimated_duration_seconds) for p in plates],
            "windows": [(w.id, w.start, w.end) for w in unavailability],
            "active": active_job.id if active_job else None,
            "blocking_end": blocking_end,
        }
        return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def _needs_recompute(self) -> bool:
        if not self._schedule_result:
            return True

        now = datetime.now(timezone.utc)
        if self._schedule_result.next_breakpoint and now >= self._schedule_result.next_breakpoint:
            return True

        current_hash = self._compute_input_hash()
        if current_hash != self._last_input_hash:
            return True

        return False

    def invalidate_schedule(self) -> None:
        """Force schedule recalculation on next update."""
        self._schedule_result = None
        self._last_input_hash = None

    def _estimate_active_job_end(self) -> datetime | None:
        if self._printer_monitor:
            blocking_end = self._printer_monitor.get_blocking_end_time()
            if blocking_end:
                return blocking_end

        active_job = self._store.get_active_job()
        if not active_job or not active_job.started_at:
            return None

        if self._printer_monitor:
            end_time = self._printer_monitor.get_end_time()
            if end_time:
                return end_time

        plate = self._store.get_plate(active_job.plate_id)
        if not plate:
            return None

        started = datetime.fromisoformat(active_job.started_at)
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        return started + timedelta(seconds=plate.estimated_duration_seconds)

    def _run_scheduler(self) -> ScheduleResult:
        if not self._needs_recompute() and self._schedule_result:
            return self._schedule_result

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

        self._schedule_result = scheduler.calculate_schedule()
        self._last_input_hash = self._compute_input_hash()
        return self._schedule_result

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

        schedule_result = self._run_scheduler()
        schedule_data = []
        for sj in schedule_result.jobs:
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

        next_scheduled = schedule_result.jobs[0] if schedule_result.jobs else None

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
            "computed_at": schedule_result.computed_at.isoformat(),
            "next_breakpoint": schedule_result.next_breakpoint.isoformat() if schedule_result.next_breakpoint else None,
            "unavailability_windows": self._store.get_unavailability_windows(),
        }
