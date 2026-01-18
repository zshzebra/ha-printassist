"""Integration tests for PrintAssist."""

import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock, patch

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])

from custom_components.printassist.store import PrintAssistStore, Project, Part
from custom_components.printassist.const import PART_STATUS_PENDING, PART_STATUS_COMPLETED


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
        assert len(store.projects) == 1

    @pytest.mark.asyncio
    async def test_delete_project(self, store):
        project = await store.async_create_project("To Delete")
        assert len(store.projects) == 1

        deleted = await store.async_delete_project(project.id)
        assert deleted is True
        assert len(store.projects) == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent_project(self, store):
        deleted = await store.async_delete_project("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_add_part(self, store):
        project = await store.async_create_project("Project")
        part = await store.async_add_part(
            project_id=project.id,
            name="Benchy",
            filename="benchy.3mf",
            thumbnail_path="/local/thumb.png",
            estimated_duration_seconds=3600,
        )

        assert part is not None
        assert part.name == "Benchy"
        assert part.status == PART_STATUS_PENDING
        assert len(store.parts) == 1

    @pytest.mark.asyncio
    async def test_add_part_to_nonexistent_project(self, store):
        part = await store.async_add_part(
            project_id="nonexistent",
            name="Part",
            filename="part.gcode",
        )
        assert part is None

    @pytest.mark.asyncio
    async def test_update_part_status(self, store):
        project = await store.async_create_project("Project")
        part = await store.async_add_part(project.id, "Part", "part.gcode")

        updated = await store.async_update_part_status(part.id, PART_STATUS_COMPLETED)
        assert updated is True

        updated_part = await store.async_get_part(part.id)
        assert updated_part.status == PART_STATUS_COMPLETED

    @pytest.mark.asyncio
    async def test_get_pending_parts(self, store):
        project = await store.async_create_project("Project")
        await store.async_add_part(project.id, "Part1", "p1.gcode")
        await store.async_add_part(project.id, "Part2", "p2.gcode")

        part3 = await store.async_add_part(project.id, "Part3", "p3.gcode")
        await store.async_update_part_status(part3.id, PART_STATUS_COMPLETED)

        pending = store.get_pending_parts()
        assert len(pending) == 2

    @pytest.mark.asyncio
    async def test_set_part_priority(self, store):
        project = await store.async_create_project("Project")
        part = await store.async_add_part(project.id, "Part", "part.gcode")

        await store.async_set_part_priority(part.id, 10)
        updated = await store.async_get_part(part.id)
        assert updated.priority == 10

    @pytest.mark.asyncio
    async def test_delete_project_cascades_parts(self, store):
        project = await store.async_create_project("Project")
        await store.async_add_part(project.id, "Part1", "p1.gcode")
        await store.async_add_part(project.id, "Part2", "p2.gcode")

        assert len(store.parts) == 2

        await store.async_delete_project(project.id)
        assert len(store.parts) == 0

    @pytest.mark.asyncio
    async def test_create_and_complete_job(self, store):
        project = await store.async_create_project("Project")
        part = await store.async_add_part(project.id, "Part", "part.gcode")

        job = await store.async_create_job(part.id)
        assert job is not None
        assert job.part_id == part.id
        assert job.status == "printing"

        active = store.get_active_job()
        assert active is not None
        assert active.id == job.id

        await store.async_complete_job(job.id)
        active = store.get_active_job()
        assert active is None

    @pytest.mark.asyncio
    async def test_unavailability_windows(self, store):
        from datetime import datetime

        start = datetime(2024, 1, 15, 22, 0)
        end = datetime(2024, 1, 16, 7, 0)

        window = await store.async_add_unavailability(start, end)
        assert window is not None
        assert len(store.unavailability_windows) == 1

        await store.async_remove_unavailability(window.id)
        assert len(store.unavailability_windows) == 0
