"""Tests for PrintAssist coordinator."""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])

with patch("homeassistant.helpers.update_coordinator.DataUpdateCoordinator.__init__", return_value=None):
    from custom_components.printassist.coordinator import PrintAssistCoordinator


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.get_queued_jobs = MagicMock(return_value=[])
    store.get_plates = MagicMock(return_value=[])
    store.get_unavailability_windows = MagicMock(return_value=[])
    store.get_active_job = MagicMock(return_value=None)
    store.get_plate = MagicMock(return_value=None)
    return store


@pytest.fixture
def mock_printer_monitor():
    monitor = MagicMock()
    monitor.get_blocking_end_time = MagicMock(return_value=None)
    monitor.get_end_time = MagicMock(return_value=None)
    return monitor


def make_coordinator(mock_store, mock_printer_monitor=None):
    coordinator = object.__new__(PrintAssistCoordinator)
    coordinator._store = mock_store
    coordinator._printer_monitor = mock_printer_monitor
    coordinator._schedule_result = None
    coordinator._last_input_hash = None
    return coordinator


class TestInputHashWithActiveJobEnd:
    def test_hash_includes_unknown_print_end_time(self, mock_store, mock_printer_monitor):
        end_time = datetime(2024, 1, 15, 18, 0, 0, tzinfo=timezone.utc)
        mock_printer_monitor.get_blocking_end_time.return_value = end_time

        coordinator = make_coordinator(mock_store, mock_printer_monitor)
        hash1 = coordinator._compute_input_hash()

        new_end_time = datetime(2024, 1, 15, 19, 30, 0, tzinfo=timezone.utc)
        mock_printer_monitor.get_blocking_end_time.return_value = new_end_time
        hash2 = coordinator._compute_input_hash()

        assert hash1 != hash2

    def test_hash_includes_known_job_end_time(self, mock_store, mock_printer_monitor):
        active_job = MagicMock()
        active_job.id = "job-1"
        active_job.plate_id = "plate-1"
        active_job.started_at = "2024-01-15T16:00:00+00:00"
        mock_store.get_active_job.return_value = active_job

        mock_printer_monitor.get_blocking_end_time.return_value = None
        end_time = datetime(2024, 1, 15, 18, 0, 0, tzinfo=timezone.utc)
        mock_printer_monitor.get_end_time.return_value = end_time

        coordinator = make_coordinator(mock_store, mock_printer_monitor)
        hash1 = coordinator._compute_input_hash()

        new_end_time = datetime(2024, 1, 15, 18, 30, 0, tzinfo=timezone.utc)
        mock_printer_monitor.get_end_time.return_value = new_end_time
        hash2 = coordinator._compute_input_hash()

        assert hash1 != hash2

    def test_hash_stable_when_end_time_unchanged(self, mock_store, mock_printer_monitor):
        end_time = datetime(2024, 1, 15, 18, 0, 0, tzinfo=timezone.utc)
        mock_printer_monitor.get_blocking_end_time.return_value = end_time

        coordinator = make_coordinator(mock_store, mock_printer_monitor)
        hash1 = coordinator._compute_input_hash()
        hash2 = coordinator._compute_input_hash()

        assert hash1 == hash2

    def test_hash_without_printer_monitor(self, mock_store):
        coordinator = make_coordinator(mock_store)
        hash1 = coordinator._compute_input_hash()
        hash2 = coordinator._compute_input_hash()

        assert hash1 == hash2

    def test_hash_falls_back_to_plate_duration(self, mock_store, mock_printer_monitor):
        active_job = MagicMock()
        active_job.id = "job-1"
        active_job.plate_id = "plate-1"
        active_job.started_at = "2024-01-15T16:00:00"
        mock_store.get_active_job.return_value = active_job

        plate = MagicMock()
        plate.estimated_duration_seconds = 3600
        mock_store.get_plate.return_value = plate

        mock_printer_monitor.get_blocking_end_time.return_value = None
        mock_printer_monitor.get_end_time.return_value = None

        coordinator = make_coordinator(mock_store, mock_printer_monitor)
        hash1 = coordinator._compute_input_hash()

        plate.estimated_duration_seconds = 7200
        hash2 = coordinator._compute_input_hash()

        assert hash1 != hash2
