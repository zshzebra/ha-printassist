"""Tests for PrintAssist scheduler."""

import pytest
from datetime import datetime, timedelta, timezone

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])

from custom_components.printassist.scheduler import PrintScheduler, ScheduledJob, ScheduleResult
from custom_components.printassist.store import Plate, Job, UnavailabilityWindow


def utc(*args) -> datetime:
    """Create a UTC-aware datetime."""
    return datetime(*args, tzinfo=timezone.utc)


def make_plate(id: str, name: str, duration: int, priority: int = 0) -> Plate:
    """Helper to create a test plate."""
    return Plate(
        id=id,
        project_id="proj-1",
        source_filename=f"{name}.3mf",
        plate_number=1,
        name=name,
        gcode_path=f"proj-1_{id}",
        estimated_duration_seconds=duration,
        thumbnail_path=None,
        quantity_needed=1,
        priority=priority,
    )


def make_job(id: str, plate_id: str) -> Job:
    """Helper to create a test job."""
    return Job(
        id=id,
        plate_id=plate_id,
        status="queued",
        created_at=datetime.now().isoformat(),
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
        scheduler = PrintScheduler([], {}, [])
        result = scheduler.calculate_schedule()
        assert isinstance(result, ScheduleResult)
        assert result.jobs == []
        assert result.next_breakpoint is None
        assert scheduler.get_next_recommended() is None

    def test_single_job_no_windows(self):
        plate = make_plate("p1", "Benchy", 3600)
        job = make_job("j1", "p1")
        scheduler = PrintScheduler([job], {"p1": plate}, [])

        result = scheduler.calculate_schedule()
        assert len(result.jobs) == 1
        assert result.jobs[0].job_id == "j1"
        assert result.jobs[0].plate_id == "p1"
        assert result.jobs[0].spans_unavailability is False
        assert result.next_breakpoint is None

    def test_priority_ordering(self):
        plates = {
            "p1": make_plate("p1", "Low", 1800, priority=0),
            "p2": make_plate("p2", "High", 1800, priority=10),
            "p3": make_plate("p3", "Medium", 1800, priority=5),
        }
        jobs = [
            make_job("j1", "p1"),
            make_job("j2", "p2"),
            make_job("j3", "p3"),
        ]
        scheduler = PrintScheduler(jobs, plates, [])

        result = scheduler.calculate_schedule()
        assert [s.job_id for s in result.jobs] == ["j2", "j3", "j1"]

    def test_fits_before_unavailability(self):
        now = utc(2024, 1, 15, 18, 0, 0)
        window = make_window("w1", utc(2024, 1, 15, 22, 0, 0), utc(2024, 1, 16, 7, 0, 0))

        plate = make_plate("p1", "ShortPrint", 3600)
        job = make_job("j1", "p1")
        scheduler = PrintScheduler([job], {"p1": plate}, [window], current_time=now)

        result = scheduler.calculate_schedule()
        assert len(result.jobs) == 1
        assert result.jobs[0].spans_unavailability is False
        assert result.jobs[0].scheduled_end <= utc(2024, 1, 15, 22, 0, 0)

    def test_does_not_fit_spans_short_unavail(self):
        now = utc(2024, 1, 15, 20, 0, 0)
        window = make_window("w1", utc(2024, 1, 15, 22, 0, 0), utc(2024, 1, 15, 23, 30, 0))

        plate = make_plate("p1", "LongPrint", 7201)
        job = make_job("j1", "p1")
        scheduler = PrintScheduler([job], {"p1": plate}, [window], current_time=now)

        result = scheduler.calculate_schedule()
        assert len(result.jobs) == 1
        assert result.jobs[0].scheduled_start == now
        assert result.jobs[0].spans_unavailability is True

    def test_selects_fitting_job_over_priority(self):
        now = utc(2024, 1, 15, 20, 0, 0)
        window = make_window("w1", utc(2024, 1, 15, 22, 0, 0), utc(2024, 1, 16, 7, 0, 0))

        plates = {
            "p1": make_plate("p1", "Long", 10800, priority=10),
            "p2": make_plate("p2", "Short", 3600, priority=5),
        }
        jobs = [
            make_job("j1", "p1"),
            make_job("j2", "p2"),
        ]
        scheduler = PrintScheduler(jobs, plates, [window], current_time=now)

        result = scheduler.calculate_schedule()
        assert result.jobs[0].job_id == "j2"
        assert result.jobs[0].spans_unavailability is False

    def test_printer_busy(self):
        now = utc(2024, 1, 15, 18, 0, 0)
        busy_until = utc(2024, 1, 15, 19, 0, 0)

        plate = make_plate("p1", "Next", 1800)
        job = make_job("j1", "p1")
        scheduler = PrintScheduler([job], {"p1": plate}, [], current_time=now, active_job_end=busy_until)

        result = scheduler.calculate_schedule()
        assert result.jobs[0].scheduled_start == busy_until

    def test_get_next_recommended(self):
        plates = {
            "p1": make_plate("p1", "First", 1800, priority=10),
            "p2": make_plate("p2", "Second", 1800, priority=5),
        }
        jobs = [
            make_job("j1", "p1"),
            make_job("j2", "p2"),
        ]
        scheduler = PrintScheduler(jobs, plates, [])

        recommended = scheduler.get_next_recommended()
        assert recommended is not None
        assert recommended.job_id == "j1"
        assert recommended.plate_name == "First"

    def test_multiple_windows(self):
        now = utc(2024, 1, 15, 8, 0, 0)
        windows = [
            make_window("w1", utc(2024, 1, 15, 9, 0, 0), utc(2024, 1, 15, 10, 0, 0)),
            make_window("w2", utc(2024, 1, 15, 12, 0, 0), utc(2024, 1, 15, 13, 0, 0)),
        ]

        plate = make_plate("p1", "Print", 1800)
        job = make_job("j1", "p1")
        scheduler = PrintScheduler([job], {"p1": plate}, windows, current_time=now)

        result = scheduler.calculate_schedule()
        assert result.jobs[0].scheduled_end <= utc(2024, 1, 15, 9, 0, 0)

    def test_starts_after_current_unavailability(self):
        now = utc(2024, 1, 15, 23, 0, 0)
        window = make_window("w1", utc(2024, 1, 15, 22, 0, 0), utc(2024, 1, 16, 7, 0, 0))

        plate = make_plate("p1", "Print", 1800)
        job = make_job("j1", "p1")
        scheduler = PrintScheduler([job], {"p1": plate}, [window], current_time=now)

        result = scheduler.calculate_schedule()
        assert result.jobs[0].scheduled_start >= utc(2024, 1, 16, 7, 0, 0)

    def test_long_unavailability_spans(self):
        now = utc(2024, 1, 15, 21, 0, 0)
        window = make_window("w1", utc(2024, 1, 15, 22, 0, 0), utc(2024, 1, 16, 7, 0, 0))

        plate = make_plate("p1", "LongPrint", 14400)
        job = make_job("j1", "p1")
        scheduler = PrintScheduler([job], {"p1": plate}, [window], current_time=now)

        result = scheduler.calculate_schedule()
        assert len(result.jobs) == 1
        assert result.jobs[0].spans_unavailability is True

    def test_schedule_has_timestamps(self):
        now = utc(2024, 1, 15, 18, 0, 0)
        plate = make_plate("p1", "Test", 3600)
        job = make_job("j1", "p1")
        scheduler = PrintScheduler([job], {"p1": plate}, [], current_time=now)

        result = scheduler.calculate_schedule()
        assert result.jobs[0].scheduled_start == now
        assert result.jobs[0].scheduled_end == now + timedelta(hours=1)
        assert result.jobs[0].estimated_duration_seconds == 3600

    def test_schedule_result_has_computed_at(self):
        now = utc(2024, 1, 15, 18, 0, 0)
        plate = make_plate("p1", "Test", 3600)
        job = make_job("j1", "p1")
        scheduler = PrintScheduler([job], {"p1": plate}, [], current_time=now)

        result = scheduler.calculate_schedule()
        assert result.computed_at == now
        assert result.cursor_at_computation == now

    def test_breakpoint_when_job_fits_before_unavailability(self):
        now = utc(2024, 1, 15, 18, 0, 0)
        window = make_window("w1", utc(2024, 1, 15, 22, 0, 0), utc(2024, 1, 16, 7, 0, 0))

        plate = make_plate("p1", "TwoHourPrint", 7200)
        job = make_job("j1", "p1")
        scheduler = PrintScheduler([job], {"p1": plate}, [window], current_time=now)

        result = scheduler.calculate_schedule()
        assert result.next_breakpoint == utc(2024, 1, 15, 20, 0, 0)

    def test_breakpoint_is_unavail_start_when_job_wont_fit_soon(self):
        now = utc(2024, 1, 15, 19, 30, 0)
        window = make_window("w1", utc(2024, 1, 15, 22, 0, 0), utc(2024, 1, 16, 7, 0, 0))

        plate = make_plate("p1", "ThreeHourPrint", 10800)
        job = make_job("j1", "p1")
        scheduler = PrintScheduler([job], {"p1": plate}, [window], current_time=now)

        result = scheduler.calculate_schedule()
        assert result.next_breakpoint == utc(2024, 1, 15, 22, 0, 0)

    def test_no_breakpoint_without_unavailability(self):
        now = utc(2024, 1, 15, 18, 0, 0)
        plate = make_plate("p1", "Test", 3600)
        job = make_job("j1", "p1")
        scheduler = PrintScheduler([job], {"p1": plate}, [], current_time=now)

        result = scheduler.calculate_schedule()
        assert result.next_breakpoint is None
