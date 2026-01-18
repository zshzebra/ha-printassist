"""Tests for PrintAssist scheduler."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])

from custom_components.printassist.scheduler import PrintScheduler, ScheduledPrint
from custom_components.printassist.store import Part, UnavailabilityWindow


def make_part(id: str, name: str, duration: int, priority: int = 0) -> Part:
    """Helper to create a test part."""
    return Part(
        id=id,
        project_id="proj-1",
        name=name,
        filename=f"{name}.gcode",
        thumbnail_path=None,
        estimated_duration_seconds=duration,
        filament_type=None,
        status="pending",
        priority=priority,
    )


def make_window(id: str, start: datetime, end: datetime) -> UnavailabilityWindow:
    """Helper to create unavailability window."""
    return UnavailabilityWindow(
        id=id,
        start=start.isoformat(),
        end=end.isoformat(),
    )


class TestPrintScheduler:
    def test_empty_queue(self):
        scheduler = PrintScheduler([], [])
        assert scheduler.calculate_schedule() == []
        assert scheduler.get_next_recommended() is None

    def test_single_part_no_windows(self):
        parts = [make_part("p1", "Benchy", 3600)]
        scheduler = PrintScheduler(parts, [])

        schedule = scheduler.calculate_schedule()
        assert len(schedule) == 1
        assert schedule[0].part_id == "p1"
        assert schedule[0].fits_in_window is True

    def test_priority_ordering(self):
        parts = [
            make_part("p1", "Low", 1800, priority=0),
            make_part("p2", "High", 1800, priority=10),
            make_part("p3", "Medium", 1800, priority=5),
        ]
        scheduler = PrintScheduler(parts, [])

        schedule = scheduler.calculate_schedule()
        assert [s.part_id for s in schedule] == ["p2", "p3", "p1"]

    def test_fits_before_unavailability(self):
        now = datetime(2024, 1, 15, 18, 0, 0)
        window = make_window("w1", datetime(2024, 1, 15, 22, 0, 0), datetime(2024, 1, 16, 7, 0, 0))

        parts = [make_part("p1", "ShortPrint", 3600)]  # 1 hour, fits before 10pm
        scheduler = PrintScheduler(parts, [window], current_time=now)

        schedule = scheduler.calculate_schedule()
        assert len(schedule) == 1
        assert schedule[0].fits_in_window is True
        assert schedule[0].estimated_end <= datetime(2024, 1, 15, 22, 0, 0)

    def test_does_not_fit_schedules_after(self):
        now = datetime(2024, 1, 15, 20, 0, 0)
        window = make_window("w1", datetime(2024, 1, 15, 22, 0, 0), datetime(2024, 1, 16, 7, 0, 0))

        parts = [make_part("p1", "LongPrint", 7201)]  # 2+ hours, won't finish before 10pm
        scheduler = PrintScheduler(parts, [window], current_time=now)

        schedule = scheduler.calculate_schedule()
        assert len(schedule) == 1
        assert schedule[0].estimated_start >= datetime(2024, 1, 16, 7, 0, 0)

    def test_selects_fitting_part_over_priority(self):
        now = datetime(2024, 1, 15, 20, 0, 0)
        window = make_window("w1", datetime(2024, 1, 15, 22, 0, 0), datetime(2024, 1, 16, 7, 0, 0))

        parts = [
            make_part("p1", "Long", 10800, priority=10),  # 3 hours, high priority but won't fit
            make_part("p2", "Short", 3600, priority=5),   # 1 hour, lower priority but fits
        ]
        scheduler = PrintScheduler(parts, [window], current_time=now)

        schedule = scheduler.calculate_schedule()
        assert schedule[0].part_id == "p2"
        assert schedule[0].fits_in_window is True

    def test_printer_busy(self):
        now = datetime(2024, 1, 15, 18, 0, 0)
        busy_until = datetime(2024, 1, 15, 19, 0, 0)

        parts = [make_part("p1", "Next", 1800)]
        scheduler = PrintScheduler(parts, [], current_time=now, printer_busy_until=busy_until)

        schedule = scheduler.calculate_schedule()
        assert schedule[0].estimated_start == busy_until

    def test_get_next_recommended(self):
        parts = [
            make_part("p1", "First", 1800, priority=10),
            make_part("p2", "Second", 1800, priority=5),
        ]
        scheduler = PrintScheduler(parts, [])

        recommended = scheduler.get_next_recommended()
        assert recommended is not None
        assert recommended.id == "p1"
        assert recommended.name == "First"

    def test_multiple_windows(self):
        now = datetime(2024, 1, 15, 8, 0, 0)
        windows = [
            make_window("w1", datetime(2024, 1, 15, 9, 0, 0), datetime(2024, 1, 15, 10, 0, 0)),
            make_window("w2", datetime(2024, 1, 15, 12, 0, 0), datetime(2024, 1, 15, 13, 0, 0)),
        ]

        parts = [make_part("p1", "Print", 1800)]  # 30 min
        scheduler = PrintScheduler(parts, windows, current_time=now)

        schedule = scheduler.calculate_schedule()
        assert schedule[0].estimated_end <= datetime(2024, 1, 15, 9, 0, 0)

    def test_starts_after_current_unavailability(self):
        now = datetime(2024, 1, 15, 23, 0, 0)
        window = make_window("w1", datetime(2024, 1, 15, 22, 0, 0), datetime(2024, 1, 16, 7, 0, 0))

        parts = [make_part("p1", "Print", 1800)]
        scheduler = PrintScheduler(parts, [window], current_time=now)

        schedule = scheduler.calculate_schedule()
        assert schedule[0].estimated_start >= datetime(2024, 1, 16, 7, 0, 0)
