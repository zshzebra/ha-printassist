"""Tests for Bambu printer monitor."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock, patch

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])

from custom_components.printassist.printer_monitor import BambuPrinterMonitor
from custom_components.printassist.const import (
    BAMBU_STATUS_RUNNING,
    BAMBU_STATUS_IDLE,
    BAMBU_STATUS_FINISH,
)


def make_entity_entry(entity_id: str):
    entry = MagicMock()
    entry.entity_id = entity_id
    return entry


def make_entity_registry(entities: list[str]):
    reg = MagicMock()
    entries = [make_entity_entry(e) for e in entities]
    return reg, entries


@pytest.fixture
def mock_hass_with_bambu():
    hass = MagicMock()
    hass.states = MagicMock()
    hass.bus = MagicMock()
    hass.bus.async_listen = MagicMock(return_value=MagicMock())
    hass.async_create_task = MagicMock(side_effect=lambda coro: coro)
    return hass


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.get_queued_jobs = MagicMock(return_value=[])
    store.get_active_job = MagicMock(return_value=None)
    store.get_plate = MagicMock(return_value=None)
    store.async_start_job = AsyncMock(return_value=True)
    store.async_complete_job = AsyncMock(return_value=True)
    return store


@pytest.fixture
def on_schedule_change():
    return MagicMock()


@pytest.fixture
def standard_entities():
    return [
        "sensor.p1p_01s00d522100740_print_status",
        "sensor.p1p_01s00d522100740_end_time",
        "sensor.p1p_01s00d522100740_task_name",
        "sensor.p1p_01s00d522100740_gcode_filename",
    ]


class TestBambuPrinterMonitor:
    def test_entity_resolution_from_device(self, mock_hass_with_bambu, mock_store, on_schedule_change, standard_entities):
        reg, entries = make_entity_registry(standard_entities)

        with patch("custom_components.printassist.printer_monitor.er.async_get", return_value=reg), \
             patch("custom_components.printassist.printer_monitor.er.async_entries_for_device", return_value=entries):
            monitor = BambuPrinterMonitor(
                mock_hass_with_bambu,
                "device-123",
                mock_store,
                on_schedule_change,
            )
            assert monitor._resolve_entities() is True
            assert monitor.status_entity == "sensor.p1p_01s00d522100740_print_status"
            assert monitor.end_time_entity == "sensor.p1p_01s00d522100740_end_time"
            assert monitor.task_name_entity == "sensor.p1p_01s00d522100740_task_name"
            assert monitor.gcode_filename_entity == "sensor.p1p_01s00d522100740_gcode_filename"

    def test_entity_resolution_fails_without_status(self, mock_hass_with_bambu, mock_store, on_schedule_change):
        entities = ["sensor.p1p_end_time", "sensor.p1p_task_name"]
        reg, entries = make_entity_registry(entities)

        with patch("custom_components.printassist.printer_monitor.er.async_get", return_value=reg), \
             patch("custom_components.printassist.printer_monitor.er.async_entries_for_device", return_value=entries):
            monitor = BambuPrinterMonitor(
                mock_hass_with_bambu,
                "device-123",
                mock_store,
                on_schedule_change,
            )
            assert monitor._resolve_entities() is False

    @pytest.mark.asyncio
    async def test_setup_fails_when_entity_not_found(self, mock_hass_with_bambu, mock_store, on_schedule_change, standard_entities):
        reg, entries = make_entity_registry(standard_entities)
        mock_hass_with_bambu.states.get = MagicMock(return_value=None)

        with patch("custom_components.printassist.printer_monitor.er.async_get", return_value=reg), \
             patch("custom_components.printassist.printer_monitor.er.async_entries_for_device", return_value=entries):
            monitor = BambuPrinterMonitor(
                mock_hass_with_bambu,
                "device-123",
                mock_store,
                on_schedule_change,
            )
            result = await monitor.async_setup()
            assert result is False

    @pytest.mark.asyncio
    async def test_setup_succeeds_when_entity_exists(self, mock_hass_with_bambu, mock_store, on_schedule_change, standard_entities):
        reg, entries = make_entity_registry(standard_entities)
        state = MagicMock()
        state.state = BAMBU_STATUS_IDLE
        mock_hass_with_bambu.states.get = MagicMock(return_value=state)

        with patch("custom_components.printassist.printer_monitor.er.async_get", return_value=reg), \
             patch("custom_components.printassist.printer_monitor.er.async_entries_for_device", return_value=entries):
            monitor = BambuPrinterMonitor(
                mock_hass_with_bambu,
                "device-123",
                mock_store,
                on_schedule_change,
            )
            result = await monitor.async_setup()
            assert result is True
            mock_hass_with_bambu.bus.async_listen.assert_called_once()

    def test_get_end_time_parses_datetime(self, mock_hass_with_bambu, mock_store, on_schedule_change):
        state = MagicMock()
        state.state = "2024-01-15T17:35:00"
        mock_hass_with_bambu.states.get = MagicMock(return_value=state)

        monitor = BambuPrinterMonitor(
            mock_hass_with_bambu,
            "device-123",
            mock_store,
            on_schedule_change,
        )
        monitor._end_time_entity = "sensor.p1p_end_time"

        end_time = monitor.get_end_time()
        assert end_time is not None
        assert end_time.year == 2024
        assert end_time.month == 1
        assert end_time.day == 15
        assert end_time.hour == 17
        assert end_time.minute == 35

    def test_get_end_time_returns_none_for_unavailable(self, mock_hass_with_bambu, mock_store, on_schedule_change):
        state = MagicMock()
        state.state = "unavailable"
        mock_hass_with_bambu.states.get = MagicMock(return_value=state)

        monitor = BambuPrinterMonitor(
            mock_hass_with_bambu,
            "device-123",
            mock_store,
            on_schedule_change,
        )
        monitor._end_time_entity = "sensor.p1p_end_time"
        assert monitor.get_end_time() is None

    def test_get_end_time_returns_none_for_missing_entity(self, mock_hass_with_bambu, mock_store, on_schedule_change):
        monitor = BambuPrinterMonitor(
            mock_hass_with_bambu,
            "device-123",
            mock_store,
            on_schedule_change,
        )
        monitor._end_time_entity = None
        assert monitor.get_end_time() is None

    def test_is_printing(self, mock_hass_with_bambu, mock_store, on_schedule_change):
        monitor = BambuPrinterMonitor(
            mock_hass_with_bambu,
            "device-123",
            mock_store,
            on_schedule_change,
        )
        monitor._last_status = BAMBU_STATUS_RUNNING
        assert monitor.is_printing() is True

        monitor._last_status = BAMBU_STATUS_IDLE
        assert monitor.is_printing() is False


class TestJobMatching:
    def test_match_by_source_filename(self, mock_hass_with_bambu, mock_store, on_schedule_change):
        job = MagicMock()
        job.id = "job-1"
        job.plate_id = "plate-1"

        plate = MagicMock()
        plate.source_filename = "benchy.3mf"

        mock_store.get_queued_jobs.return_value = [job]
        mock_store.get_plate.return_value = plate

        monitor = BambuPrinterMonitor(
            mock_hass_with_bambu,
            "device-123",
            mock_store,
            on_schedule_change,
        )

        matched = monitor._match_job_to_task("benchy_PLA-BASIC_2h30m.gcode.3mf")
        assert matched is not None
        assert matched.id == "job-1"

    def test_match_by_stem(self, mock_hass_with_bambu, mock_store, on_schedule_change):
        job = MagicMock()
        job.id = "job-1"
        job.plate_id = "plate-1"

        plate = MagicMock()
        plate.source_filename = "My_Model_v2.3mf"

        mock_store.get_queued_jobs.return_value = [job]
        mock_store.get_plate.return_value = plate

        monitor = BambuPrinterMonitor(
            mock_hass_with_bambu,
            "device-123",
            mock_store,
            on_schedule_change,
        )

        matched = monitor._match_job_to_task("My_Model_v2_PLA_4h.gcode.3mf")
        assert matched is not None

    def test_no_match_returns_none(self, mock_hass_with_bambu, mock_store, on_schedule_change):
        job = MagicMock()
        job.id = "job-1"
        job.plate_id = "plate-1"

        plate = MagicMock()
        plate.source_filename = "benchy.3mf"

        mock_store.get_queued_jobs.return_value = [job]
        mock_store.get_plate.return_value = plate

        monitor = BambuPrinterMonitor(
            mock_hass_with_bambu,
            "device-123",
            mock_store,
            on_schedule_change,
        )

        matched = monitor._match_job_to_task("completely_different_model.gcode.3mf")
        assert matched is None


class TestStatusHandling:
    @pytest.mark.asyncio
    async def test_print_started_auto_starts_job(self, mock_hass_with_bambu, mock_store, on_schedule_change):
        job = MagicMock()
        job.id = "job-1"
        job.plate_id = "plate-1"

        plate = MagicMock()
        plate.source_filename = "benchy.3mf"

        mock_store.get_queued_jobs.return_value = [job]
        mock_store.get_plate.return_value = plate
        mock_store.get_active_job.return_value = None

        task_state = MagicMock()
        task_state.state = "benchy_PLA_2h.gcode.3mf"
        mock_hass_with_bambu.states.get = MagicMock(return_value=task_state)

        monitor = BambuPrinterMonitor(
            mock_hass_with_bambu,
            "device-123",
            mock_store,
            on_schedule_change,
        )
        monitor._task_name_entity = "sensor.p1p_task_name"

        await monitor._handle_print_started()

        mock_store.async_start_job.assert_called_once_with("job-1")
        on_schedule_change.assert_called_once()

    @pytest.mark.asyncio
    async def test_print_completed_auto_completes_job(self, mock_hass_with_bambu, mock_store, on_schedule_change):
        active_job = MagicMock()
        active_job.id = "job-1"
        mock_store.get_active_job.return_value = active_job

        monitor = BambuPrinterMonitor(
            mock_hass_with_bambu,
            "device-123",
            mock_store,
            on_schedule_change,
        )

        await monitor._handle_print_completed()

        mock_store.async_complete_job.assert_called_once_with("job-1")
        on_schedule_change.assert_called_once()

    @pytest.mark.asyncio
    async def test_print_completed_no_active_job(self, mock_hass_with_bambu, mock_store, on_schedule_change):
        mock_store.get_active_job.return_value = None

        monitor = BambuPrinterMonitor(
            mock_hass_with_bambu,
            "device-123",
            mock_store,
            on_schedule_change,
        )

        await monitor._handle_print_completed()

        mock_store.async_complete_job.assert_not_called()
        on_schedule_change.assert_not_called()


class TestUnknownPrintBlocking:
    def test_get_blocking_end_time_none_when_no_unknown_print(self, mock_hass_with_bambu, mock_store, on_schedule_change):
        monitor = BambuPrinterMonitor(
            mock_hass_with_bambu,
            "device-123",
            mock_store,
            on_schedule_change,
        )
        assert monitor.get_blocking_end_time() is None

    def test_get_blocking_end_time_uses_sensor_when_available(self, mock_hass_with_bambu, mock_store, on_schedule_change):
        end_time_state = MagicMock()
        end_time_state.state = "2024-01-15T18:00:00"
        mock_hass_with_bambu.states.get = MagicMock(return_value=end_time_state)

        monitor = BambuPrinterMonitor(
            mock_hass_with_bambu,
            "device-123",
            mock_store,
            on_schedule_change,
        )
        monitor._end_time_entity = "sensor.p1p_end_time"
        monitor._unknown_print_detected_at = datetime(2024, 1, 15, 16, 0, 0, tzinfo=timezone.utc)
        monitor._unknown_print_task_name = "some_print.gcode"

        blocking_end = monitor.get_blocking_end_time()
        assert blocking_end is not None
        assert blocking_end.hour == 18

    def test_get_blocking_end_time_fallback_to_one_hour(self, mock_hass_with_bambu, mock_store, on_schedule_change):
        mock_hass_with_bambu.states.get = MagicMock(return_value=None)

        monitor = BambuPrinterMonitor(
            mock_hass_with_bambu,
            "device-123",
            mock_store,
            on_schedule_change,
        )
        monitor._end_time_entity = None
        detected_at = datetime(2024, 1, 15, 16, 0, 0, tzinfo=timezone.utc)
        monitor._unknown_print_detected_at = detected_at
        monitor._unknown_print_task_name = "some_print.gcode"

        blocking_end = monitor.get_blocking_end_time()
        assert blocking_end == detected_at + timedelta(hours=1)

    @pytest.mark.asyncio
    async def test_unknown_print_detected_when_no_match(self, mock_hass_with_bambu, mock_store, on_schedule_change):
        mock_store.get_queued_jobs.return_value = []
        mock_store.get_active_job.return_value = None

        task_state = MagicMock()
        task_state.state = "unknown_model.gcode.3mf"
        mock_hass_with_bambu.states.get = MagicMock(return_value=task_state)

        monitor = BambuPrinterMonitor(
            mock_hass_with_bambu,
            "device-123",
            mock_store,
            on_schedule_change,
        )
        monitor._task_name_entity = "sensor.p1p_task_name"

        await monitor._handle_print_started()

        assert monitor._unknown_print_detected_at is not None
        assert monitor._unknown_print_task_name == "unknown_model.gcode.3mf"
        mock_store.async_start_job.assert_not_called()
        on_schedule_change.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_print_cleared_on_completion(self, mock_hass_with_bambu, mock_store, on_schedule_change):
        mock_store.get_active_job.return_value = None

        monitor = BambuPrinterMonitor(
            mock_hass_with_bambu,
            "device-123",
            mock_store,
            on_schedule_change,
        )
        monitor._unknown_print_detected_at = datetime.now(timezone.utc)
        monitor._unknown_print_task_name = "unknown_model.gcode"

        await monitor._handle_print_completed()

        assert monitor._unknown_print_detected_at is None
        assert monitor._unknown_print_task_name is None
        mock_store.async_complete_job.assert_not_called()
        on_schedule_change.assert_called_once()

    @pytest.mark.asyncio
    async def test_known_print_clears_unknown_state(self, mock_hass_with_bambu, mock_store, on_schedule_change):
        job = MagicMock()
        job.id = "job-1"
        job.plate_id = "plate-1"

        plate = MagicMock()
        plate.source_filename = "benchy.3mf"

        mock_store.get_queued_jobs.return_value = [job]
        mock_store.get_plate.return_value = plate
        mock_store.get_active_job.return_value = None

        task_state = MagicMock()
        task_state.state = "benchy_PLA_2h.gcode.3mf"
        mock_hass_with_bambu.states.get = MagicMock(return_value=task_state)

        monitor = BambuPrinterMonitor(
            mock_hass_with_bambu,
            "device-123",
            mock_store,
            on_schedule_change,
        )
        monitor._task_name_entity = "sensor.p1p_task_name"
        monitor._unknown_print_detected_at = datetime.now(timezone.utc)
        monitor._unknown_print_task_name = "old_unknown.gcode"

        await monitor._handle_print_started()

        assert monitor._unknown_print_detected_at is None
        assert monitor._unknown_print_task_name is None
        mock_store.async_start_job.assert_called_once_with("job-1")
