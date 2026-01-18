"""Bambu Lab printer monitoring for PrintAssist."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, callback
from homeassistant.helpers import entity_registry as er

from .const import (
    BAMBU_STATUS_FINISH,
    BAMBU_STATUS_IDLE,
    BAMBU_STATUS_RUNNING,
    BAMBU_SUFFIX_END_TIME,
    BAMBU_SUFFIX_GCODE_FILENAME,
    BAMBU_SUFFIX_STATUS,
    BAMBU_SUFFIX_TASK_NAME,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from .store import PrintAssistStore, Job

_LOGGER = logging.getLogger(__name__)


class BambuPrinterMonitor:
    def __init__(
        self,
        hass: HomeAssistant,
        device_id: str,
        store: PrintAssistStore,
        on_schedule_change: Callable[[], None],
    ) -> None:
        self._hass = hass
        self._device_id = device_id
        self._store = store
        self._on_schedule_change = on_schedule_change
        self._unsub_listener: Callable[[], None] | None = None
        self._last_status: str | None = None
        self._unknown_print_detected_at: datetime | None = None
        self._unknown_print_task_name: str | None = None
        self._status_entity: str | None = None
        self._end_time_entity: str | None = None
        self._task_name_entity: str | None = None
        self._gcode_filename_entity: str | None = None

    @property
    def status_entity(self) -> str | None:
        return self._status_entity

    @property
    def end_time_entity(self) -> str | None:
        return self._end_time_entity

    @property
    def task_name_entity(self) -> str | None:
        return self._task_name_entity

    @property
    def gcode_filename_entity(self) -> str | None:
        return self._gcode_filename_entity

    def _resolve_entities(self) -> bool:
        ent_reg = er.async_get(self._hass)
        entities = er.async_entries_for_device(ent_reg, self._device_id)

        for entry in entities:
            entity_id = entry.entity_id
            if entity_id.endswith(BAMBU_SUFFIX_STATUS):
                self._status_entity = entity_id
            elif entity_id.endswith(BAMBU_SUFFIX_END_TIME):
                self._end_time_entity = entity_id
            elif entity_id.endswith(BAMBU_SUFFIX_TASK_NAME):
                self._task_name_entity = entity_id
            elif entity_id.endswith(BAMBU_SUFFIX_GCODE_FILENAME):
                self._gcode_filename_entity = entity_id

        if not self._status_entity:
            _LOGGER.warning("No print_status entity found for device %s", self._device_id)
            return False

        _LOGGER.debug(
            "Resolved entities - status: %s, end_time: %s, task_name: %s, gcode: %s",
            self._status_entity,
            self._end_time_entity,
            self._task_name_entity,
            self._gcode_filename_entity,
        )
        return True

    async def async_setup(self) -> bool:
        if not self._resolve_entities():
            return False

        state = self._hass.states.get(self._status_entity)
        if not state:
            _LOGGER.warning("Bambu status entity not found: %s", self._status_entity)
            return False

        self._last_status = state.state
        _LOGGER.info(
            "Bambu printer monitor initialized, status: %s",
            self._last_status,
        )

        if self._last_status == BAMBU_STATUS_RUNNING:
            await self._handle_print_started()

        @callback
        def _on_state_change(event: Event) -> None:
            entity_id = event.data.get("entity_id")
            if entity_id == self._status_entity:
                self._hass.async_create_task(self._handle_status_change(event))

        self._unsub_listener = self._hass.bus.async_listen(
            EVENT_STATE_CHANGED, _on_state_change
        )
        return True

    async def async_unload(self) -> None:
        if self._unsub_listener:
            self._unsub_listener()
            self._unsub_listener = None

    async def _handle_status_change(self, event: Event) -> None:
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")

        if not new_state:
            return

        old_status = old_state.state if old_state else None
        new_status = new_state.state

        if old_status == new_status:
            return

        _LOGGER.debug("Bambu status: %s -> %s", old_status, new_status)
        self._last_status = new_status

        if new_status == BAMBU_STATUS_RUNNING:
            await self._handle_print_started()
        elif old_status == BAMBU_STATUS_RUNNING and new_status in (
            BAMBU_STATUS_FINISH,
            BAMBU_STATUS_IDLE,
        ):
            await self._handle_print_completed()

    async def _handle_print_started(self) -> None:
        task_name = self._get_task_name()
        if not task_name:
            _LOGGER.debug("Print started but no task name available")
            return

        active_job = self._store.get_active_job()
        if active_job:
            _LOGGER.debug("Print already tracked as active: %s", active_job.id)
            return

        job = self._match_job_to_task(task_name)
        if job:
            await self._store.async_start_job(job.id)
            self._unknown_print_detected_at = None
            self._unknown_print_task_name = None
            _LOGGER.info("Auto-started job %s for task: %s", job.id, task_name)
        else:
            self._unknown_print_detected_at = datetime.now(timezone.utc)
            self._unknown_print_task_name = task_name
            _LOGGER.info("Unknown print detected, blocking scheduler: %s", task_name)

        self._on_schedule_change()

    async def _handle_print_completed(self) -> None:
        if self._unknown_print_detected_at:
            _LOGGER.info("Unknown print completed: %s", self._unknown_print_task_name)
            self._unknown_print_detected_at = None
            self._unknown_print_task_name = None
            self._on_schedule_change()
            return

        active_job = self._store.get_active_job()
        if not active_job:
            _LOGGER.debug("Print completed but no active job tracked")
            return

        await self._store.async_complete_job(active_job.id)
        _LOGGER.info("Auto-completed job %s", active_job.id)
        self._on_schedule_change()

    def _get_task_name(self) -> str | None:
        for entity in (self._task_name_entity, self._gcode_filename_entity):
            if not entity:
                continue
            state = self._hass.states.get(entity)
            if state and state.state not in ("unknown", "unavailable", ""):
                return state.state
        return None

    def _match_job_to_task(self, task_name: str) -> Job | None:
        task_name_lower = task_name.lower()

        for job in self._store.get_queued_jobs():
            plate = self._store.get_plate(job.plate_id)
            if not plate:
                continue

            source_lower = plate.source_filename.lower()
            if source_lower in task_name_lower:
                return job

            base_name = Path(plate.source_filename).stem.lower()
            if base_name in task_name_lower:
                return job

            task_base = Path(task_name).stem.lower()
            if base_name in task_base or task_base in source_lower:
                return job

        return None

    def get_end_time(self) -> datetime | None:
        if not self._end_time_entity:
            return None
        state = self._hass.states.get(self._end_time_entity)
        if not state or state.state in ("unknown", "unavailable", ""):
            return None

        try:
            dt = datetime.fromisoformat(state.state)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            _LOGGER.debug("Invalid end_time format: %s", state.state)
            return None

    def is_printing(self) -> bool:
        return self._last_status == BAMBU_STATUS_RUNNING

    def get_blocking_end_time(self) -> datetime | None:
        """Return end time if printer is busy with unknown print."""
        if self._unknown_print_detected_at is None:
            return None

        end_time = self.get_end_time()
        if end_time:
            return end_time

        return self._unknown_print_detected_at + timedelta(hours=1)
