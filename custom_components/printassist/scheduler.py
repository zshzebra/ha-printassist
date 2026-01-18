"""Scheduler for optimizing print queue based on availability windows."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .store import Plate, Job, UnavailabilityWindow

LONG_UNAVAILABILITY_THRESHOLD = 3 * 3600
SCHEDULE_HORIZON_DAYS = 7


@dataclass
class ScheduleResult:
    jobs: list[ScheduledJob]
    computed_at: datetime
    cursor_at_computation: datetime
    next_breakpoint: datetime | None


def _make_aware(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware (UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_datetime(iso_str: str) -> datetime:
    """Parse ISO datetime string to timezone-aware datetime."""
    dt = datetime.fromisoformat(iso_str)
    return _make_aware(dt)


@dataclass
class ScheduledJob:
    job_id: str
    plate_id: str
    plate_name: str
    plate_number: int
    source_filename: str
    scheduled_start: datetime
    scheduled_end: datetime
    estimated_duration_seconds: int
    spans_unavailability: bool
    thumbnail_path: str | None = None


class PrintScheduler:
    """Optimizes print queue using two-phase greedy with lookahead."""

    def __init__(
        self,
        queued_jobs: list[Job],
        plates_by_id: dict[str, Plate],
        unavailability_windows: list[UnavailabilityWindow],
        current_time: datetime | None = None,
        active_job_end: datetime | None = None,
    ) -> None:
        self._queued_jobs = queued_jobs
        self._plates = plates_by_id
        self._now = _make_aware(current_time) if current_time else datetime.now(timezone.utc)
        self._cursor = _make_aware(active_job_end) if active_job_end else self._now
        self._windows = self._parse_windows(unavailability_windows)
        self._horizon = self._now + timedelta(days=SCHEDULE_HORIZON_DAYS)

    def _parse_windows(
        self, windows: list[UnavailabilityWindow]
    ) -> list[tuple[datetime, datetime]]:
        parsed = []
        for w in windows:
            start = _parse_datetime(w.start)
            end = _parse_datetime(w.end)
            if end > self._now:
                parsed.append((max(start, self._now), end))
        return sorted(parsed, key=lambda x: x[0])

    def _find_next_unavailability(self, after: datetime) -> tuple[datetime, datetime] | None:
        for start, end in self._windows:
            if start > after:
                return (start, end)
            elif start <= after < end:
                return (start, end)
        return None

    def _is_during_unavailability(self, time: datetime) -> tuple[datetime, datetime] | None:
        for start, end in self._windows:
            if start <= time < end:
                return (start, end)
        return None

    def _get_job_info(self, job: Job) -> tuple[Plate | None, int]:
        plate = self._plates.get(job.plate_id)
        if not plate:
            return None, 0
        return plate, plate.estimated_duration_seconds

    def _build_remaining(self) -> list[tuple[Job, Plate, int]]:
        remaining = []
        for job in self._queued_jobs:
            plate = self._plates.get(job.plate_id)
            if plate:
                remaining.append((job, plate, plate.estimated_duration_seconds))
        remaining.sort(key=lambda x: (-x[1].priority, -x[2]))
        return remaining

    def _calculate_breakpoint(
        self, first_job: ScheduledJob | None, cursor: datetime
    ) -> datetime | None:
        if not first_job:
            return None

        next_unavail = self._find_next_unavailability(cursor)
        if not next_unavail:
            return None

        unavail_start, unavail_end = next_unavail

        if first_job.scheduled_end <= unavail_start:
            breakpoint = unavail_start - timedelta(seconds=first_job.estimated_duration_seconds)
            if breakpoint > self._now:
                return breakpoint

        return unavail_start

    def calculate_schedule(self) -> ScheduleResult:
        schedule: list[ScheduledJob] = []
        cursor = self._cursor

        during_window = self._is_during_unavailability(cursor)
        if during_window:
            cursor = during_window[1]

        remaining = self._build_remaining()

        while remaining and cursor < self._horizon:
            next_unavail = self._find_next_unavailability(cursor)

            if next_unavail and next_unavail[0] <= cursor:
                cursor = next_unavail[1]
                continue

            if next_unavail:
                available_time = (next_unavail[0] - cursor).total_seconds()
                unavail_duration = (next_unavail[1] - next_unavail[0]).total_seconds()
            else:
                available_time = float("inf")
                unavail_duration = 0

            if next_unavail and unavail_duration >= LONG_UNAVAILABILITY_THRESHOLD:
                fitting = [(j, p, d) for j, p, d in remaining if d <= available_time]
                if fitting:
                    job, plate, duration = fitting[0]
                    end_time = cursor + timedelta(seconds=duration)
                    schedule.append(ScheduledJob(
                        job_id=job.id,
                        plate_id=plate.id,
                        plate_name=plate.name,
                        plate_number=plate.plate_number,
                        source_filename=plate.source_filename,
                        scheduled_start=cursor,
                        scheduled_end=end_time,
                        estimated_duration_seconds=duration,
                        spans_unavailability=False,
                        thumbnail_path=plate.thumbnail_path,
                    ))
                    cursor = end_time
                    remaining.remove((job, plate, duration))
                else:
                    long_jobs = [(j, p, d) for j, p, d in remaining if d > available_time]
                    if long_jobs:
                        job, plate, duration = long_jobs[0]
                        end_time = cursor + timedelta(seconds=duration)
                        schedule.append(ScheduledJob(
                            job_id=job.id,
                            plate_id=plate.id,
                            plate_name=plate.name,
                            plate_number=plate.plate_number,
                            source_filename=plate.source_filename,
                            scheduled_start=cursor,
                            scheduled_end=end_time,
                            estimated_duration_seconds=duration,
                            spans_unavailability=True,
                            thumbnail_path=plate.thumbnail_path,
                        ))
                        cursor = end_time
                        remaining.remove((job, plate, duration))
                    else:
                        cursor = next_unavail[1]
            elif next_unavail:
                fitting = [(j, p, d) for j, p, d in remaining if d <= available_time]
                if fitting:
                    fitting.sort(key=lambda x: -x[2])
                    job, plate, duration = fitting[0]
                    end_time = cursor + timedelta(seconds=duration)
                    schedule.append(ScheduledJob(
                        job_id=job.id,
                        plate_id=plate.id,
                        plate_name=plate.name,
                        plate_number=plate.plate_number,
                        source_filename=plate.source_filename,
                        scheduled_start=cursor,
                        scheduled_end=end_time,
                        estimated_duration_seconds=duration,
                        spans_unavailability=False,
                        thumbnail_path=plate.thumbnail_path,
                    ))
                    cursor = end_time
                    remaining.remove((job, plate, duration))
                else:
                    cursor = next_unavail[1]
            else:
                for job, plate, duration in remaining:
                    end_time = cursor + timedelta(seconds=duration)
                    schedule.append(ScheduledJob(
                        job_id=job.id,
                        plate_id=plate.id,
                        plate_name=plate.name,
                        plate_number=plate.plate_number,
                        source_filename=plate.source_filename,
                        scheduled_start=cursor,
                        scheduled_end=end_time,
                        estimated_duration_seconds=duration,
                        spans_unavailability=False,
                        thumbnail_path=plate.thumbnail_path,
                    ))
                    cursor = end_time
                remaining = []

        first_job = schedule[0] if schedule else None
        breakpoint = self._calculate_breakpoint(first_job, self._cursor)

        return ScheduleResult(
            jobs=schedule,
            computed_at=self._now,
            cursor_at_computation=self._cursor,
            next_breakpoint=breakpoint,
        )

    def get_next_recommended(self) -> ScheduledJob | None:
        result = self.calculate_schedule()
        return result.jobs[0] if result.jobs else None
