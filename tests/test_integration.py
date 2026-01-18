"""Integration tests for PrintAssist."""

import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])

from custom_components.printassist.store import PrintAssistStore, Project, Plate, Job
from custom_components.printassist.const import (
    JOB_STATUS_QUEUED,
    JOB_STATUS_PRINTING,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
)


class TestPrintAssistStore:
    @pytest_asyncio.fixture
    async def store(self, mock_hass):
        with patch("custom_components.printassist.store.Store") as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load = AsyncMock(return_value=None)
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store

            store = PrintAssistStore(mock_hass)
            await store.async_load()
            return store

    @pytest.mark.asyncio
    async def test_create_project(self, store):
        project = await store.async_create_project("Test Project", "Some notes")

        assert project.name == "Test Project"
        assert project.notes == "Some notes"
        assert project.id is not None
        assert len(store.get_projects()) == 1

    @pytest.mark.asyncio
    async def test_delete_project(self, store):
        project = await store.async_create_project("To Delete")
        assert len(store.get_projects()) == 1

        deleted = await store.async_delete_project(project.id)
        assert deleted is True
        assert len(store.get_projects()) == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent_project(self, store):
        deleted = await store.async_delete_project("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_add_plates(self, store):
        project = await store.async_create_project("Project")

        plate = Plate.create(
            project_id=project.id,
            source_filename="benchy.3mf",
            plate_number=1,
            name="Benchy",
            gcode_path="proj_1",
            estimated_duration_seconds=3600,
            thumbnail_path="/local/thumb.png",
        )
        await store.async_add_plates([plate])

        plates = store.get_plates(project.id)
        assert len(plates) == 1
        assert plates[0].name == "Benchy"

        jobs = store.get_jobs(plate_id=plate.id)
        assert len(jobs) == 1
        assert jobs[0].status == JOB_STATUS_QUEUED

    @pytest.mark.asyncio
    async def test_set_plate_quantity(self, store):
        project = await store.async_create_project("Project")
        plate = Plate.create(
            project_id=project.id,
            source_filename="test.3mf",
            plate_number=1,
            name="Test",
            gcode_path="proj_1",
            estimated_duration_seconds=1800,
        )
        await store.async_add_plates([plate])

        queued_before = len(store.get_jobs(plate_id=plate.id, status=JOB_STATUS_QUEUED))
        assert queued_before == 1

        await store.async_set_plate_quantity(plate.id, 3)
        queued_after = len(store.get_jobs(plate_id=plate.id, status=JOB_STATUS_QUEUED))
        assert queued_after == 3

        await store.async_set_plate_quantity(plate.id, 1)
        queued_final = len(store.get_jobs(plate_id=plate.id, status=JOB_STATUS_QUEUED))
        assert queued_final == 1

    @pytest.mark.asyncio
    async def test_set_plate_priority(self, store):
        project = await store.async_create_project("Project")
        plate = Plate.create(
            project_id=project.id,
            source_filename="test.3mf",
            plate_number=1,
            name="Test",
            gcode_path="proj_1",
            estimated_duration_seconds=1800,
        )
        await store.async_add_plates([plate])

        await store.async_set_plate_priority(plate.id, 10)
        updated = store.get_plate(plate.id)
        assert updated.priority == 10

    @pytest.mark.asyncio
    async def test_delete_project_cascades(self, store):
        project = await store.async_create_project("Project")
        plate1 = Plate.create(
            project_id=project.id,
            source_filename="p1.3mf",
            plate_number=1,
            name="Plate1",
            gcode_path="proj_1",
            estimated_duration_seconds=1800,
        )
        plate2 = Plate.create(
            project_id=project.id,
            source_filename="p2.3mf",
            plate_number=1,
            name="Plate2",
            gcode_path="proj_2",
            estimated_duration_seconds=1800,
        )
        await store.async_add_plates([plate1, plate2])

        assert len(store.get_plates()) == 2
        assert len(store.get_jobs()) == 2

        await store.async_delete_project(project.id)
        assert len(store.get_plates()) == 0
        assert len(store.get_jobs()) == 0

    @pytest.mark.asyncio
    async def test_job_lifecycle(self, store):
        project = await store.async_create_project("Project")
        plate = Plate.create(
            project_id=project.id,
            source_filename="test.3mf",
            plate_number=1,
            name="Test",
            gcode_path="proj_1",
            estimated_duration_seconds=1800,
        )
        await store.async_add_plates([plate])

        jobs = store.get_queued_jobs()
        assert len(jobs) == 1
        job_id = jobs[0].id

        success = await store.async_start_job(job_id)
        assert success is True
        active = store.get_active_job()
        assert active is not None
        assert active.id == job_id
        assert active.status == JOB_STATUS_PRINTING

        success = await store.async_complete_job(job_id)
        assert success is True
        active = store.get_active_job()
        assert active is None

        job = store.get_job(job_id)
        assert job.status == JOB_STATUS_COMPLETED

    @pytest.mark.asyncio
    async def test_fail_job_creates_replacement(self, store):
        project = await store.async_create_project("Project")
        plate = Plate.create(
            project_id=project.id,
            source_filename="test.3mf",
            plate_number=1,
            name="Test",
            gcode_path="proj_1",
            estimated_duration_seconds=1800,
        )
        await store.async_add_plates([plate])

        job_id = store.get_queued_jobs()[0].id
        await store.async_start_job(job_id)

        new_job = await store.async_fail_job(job_id, "Stringing")
        assert new_job is not None

        failed_job = store.get_job(job_id)
        assert failed_job.status == JOB_STATUS_FAILED
        assert failed_job.failure_reason == "Stringing"

        queued = store.get_queued_jobs()
        assert len(queued) == 1
        assert queued[0].id == new_job.id

    @pytest.mark.asyncio
    async def test_project_progress(self, store):
        project = await store.async_create_project("Project")
        plate = Plate.create(
            project_id=project.id,
            source_filename="test.3mf",
            plate_number=1,
            name="Test",
            gcode_path="proj_1",
            estimated_duration_seconds=1800,
        )
        await store.async_add_plates([plate])
        await store.async_set_plate_quantity(plate.id, 3)

        completed, total = store.get_project_progress(project.id)
        assert completed == 0
        assert total == 3

        jobs = store.get_queued_jobs()
        await store.async_start_job(jobs[0].id)
        await store.async_complete_job(jobs[0].id)

        completed, total = store.get_project_progress(project.id)
        assert completed == 1
        assert total == 3

    @pytest.mark.asyncio
    async def test_unavailability_windows(self, store):
        start = datetime(2024, 1, 15, 22, 0)
        end = datetime(2024, 1, 16, 7, 0)

        window = await store.async_add_unavailability(start, end)
        assert window is not None
        assert len(store.get_unavailability_windows()) == 1

        await store.async_remove_unavailability(window.id)
        assert len(store.get_unavailability_windows()) == 0
