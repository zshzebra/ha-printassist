"""Scheduler for optimizing print queue based on availability windows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .store import Part, UnavailabilityWindow


@dataclass
class ScheduledPrint:
    part_id: str
    name: str
    estimated_start: datetime
    estimated_end: datetime
    fits_in_window: bool


class PrintScheduler:
    """Optimizes print queue based on availability windows."""

    def __init__(
        self,
        pending_parts: list[Part],
        unavailability_windows: list[UnavailabilityWindow],
        current_time: datetime | None = None,
        printer_busy_until: datetime | None = None,
    ) -> None:
        self._parts = sorted(pending_parts, key=lambda p: -p.priority)
        self._now = current_time or datetime.now()
        self._printer_free_at = printer_busy_until or self._now
        self._windows = self._parse_windows(unavailability_windows)

    def _parse_windows(
        self, windows: list[UnavailabilityWindow]
    ) -> list[tuple[datetime, datetime]]:
        """Parse unavailability windows into datetime tuples."""
        parsed = []
        for w in windows:
            start = datetime.fromisoformat(w.start)
            end = datetime.fromisoformat(w.end)
            if end > self._now:
                parsed.append((start, end))
        return sorted(parsed, key=lambda x: x[0])

    def _find_next_unavailability(self, after: datetime) -> tuple[datetime, datetime] | None:
        """Find the next unavailability window starting after given time."""
        for start, end in self._windows:
            if start > after:
                return (start, end)
            elif start <= after < end:
                return (start, end)
        return None

    def _is_during_unavailability(self, time: datetime) -> tuple[datetime, datetime] | None:
        """Check if a time falls during an unavailability window."""
        for start, end in self._windows:
            if start <= time < end:
                return (start, end)
        return None

    def _get_availability_end(self, start_time: datetime) -> datetime | None:
        """Get when the current availability window ends."""
        window = self._find_next_unavailability(start_time)
        if window and window[0] <= start_time:
            return None
        return window[0] if window else None

    def calculate_schedule(self) -> list[ScheduledPrint]:
        """Calculate optimized print schedule."""
        schedule: list[ScheduledPrint] = []
        current_time = self._printer_free_at

        during_window = self._is_during_unavailability(current_time)
        if during_window:
            current_time = during_window[1]

        remaining_parts = list(self._parts)

        while remaining_parts:
            availability_end = self._get_availability_end(current_time)

            if availability_end:
                available_duration = (availability_end - current_time).total_seconds()
            else:
                available_duration = float("inf")

            fitting_parts = [
                p for p in remaining_parts
                if p.estimated_duration_seconds <= available_duration
            ]

            if fitting_parts:
                next_part = fitting_parts[0]
                duration = timedelta(seconds=next_part.estimated_duration_seconds)
                schedule.append(ScheduledPrint(
                    part_id=next_part.id,
                    name=next_part.name,
                    estimated_start=current_time,
                    estimated_end=current_time + duration,
                    fits_in_window=True,
                ))
                current_time = current_time + duration
                remaining_parts.remove(next_part)
            else:
                if availability_end:
                    window = self._find_next_unavailability(current_time)
                    if window:
                        current_time = window[1]
                else:
                    next_part = remaining_parts[0]
                    duration = timedelta(seconds=next_part.estimated_duration_seconds)
                    schedule.append(ScheduledPrint(
                        part_id=next_part.id,
                        name=next_part.name,
                        estimated_start=current_time,
                        estimated_end=current_time + duration,
                        fits_in_window=False,
                    ))
                    current_time = current_time + duration
                    remaining_parts.remove(next_part)

        return schedule

    def get_next_recommended(self) -> Part | None:
        """Get the next recommended part to print."""
        schedule = self.calculate_schedule()
        if not schedule:
            return None

        for part in self._parts:
            if part.id == schedule[0].part_id:
                return part
        return None
