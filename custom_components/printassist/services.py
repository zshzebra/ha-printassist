"""Service handlers for PrintAssist."""
from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.core import ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    ATTR_PROJECT_ID,
    ATTR_PROJECT_NAME,
    ATTR_PLATE_ID,
    ATTR_JOB_ID,
    ATTR_QUANTITY,
    ATTR_PRIORITY,
    ATTR_FAILURE_REASON,
    ATTR_FILENAME,
    ATTR_FILE_CONTENT,
    ATTR_START,
    ATTR_END,
    ATTR_WINDOW_ID,
    SERVICE_CREATE_PROJECT,
    SERVICE_DELETE_PROJECT,
    SERVICE_UPLOAD_3MF,
    SERVICE_DELETE_PLATE,
    SERVICE_SET_PLATE_PRIORITY,
    SERVICE_SET_QUANTITY,
    SERVICE_START_JOB,
    SERVICE_COMPLETE_JOB,
    SERVICE_FAIL_JOB,
    SERVICE_ADD_UNAVAILABILITY,
    SERVICE_REMOVE_UNAVAILABILITY,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from .store import PrintAssistStore
    from .file_handler import FileHandler
    from .coordinator import PrintAssistCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_CREATE_PROJECT_SCHEMA = vol.Schema({
    vol.Required(ATTR_PROJECT_NAME): cv.string,
    vol.Optional("notes", default=""): cv.string,
})

SERVICE_DELETE_PROJECT_SCHEMA = vol.Schema({
    vol.Required(ATTR_PROJECT_ID): cv.string,
})

SERVICE_UPLOAD_3MF_SCHEMA = vol.Schema({
    vol.Required(ATTR_PROJECT_ID): cv.string,
    vol.Required(ATTR_FILENAME): cv.string,
    vol.Required(ATTR_FILE_CONTENT): cv.string,
})

SERVICE_DELETE_PLATE_SCHEMA = vol.Schema({
    vol.Required(ATTR_PLATE_ID): cv.string,
})

SERVICE_SET_PRIORITY_SCHEMA = vol.Schema({
    vol.Required(ATTR_PLATE_ID): cv.string,
    vol.Required(ATTR_PRIORITY): vol.Coerce(int),
})

SERVICE_SET_QUANTITY_SCHEMA = vol.Schema({
    vol.Required(ATTR_PLATE_ID): cv.string,
    vol.Required(ATTR_QUANTITY): vol.Coerce(int),
})

SERVICE_START_JOB_SCHEMA = vol.Schema({
    vol.Required(ATTR_JOB_ID): cv.string,
})

SERVICE_COMPLETE_JOB_SCHEMA = vol.Schema({
    vol.Required(ATTR_JOB_ID): cv.string,
})

SERVICE_FAIL_JOB_SCHEMA = vol.Schema({
    vol.Required(ATTR_JOB_ID): cv.string,
    vol.Optional(ATTR_FAILURE_REASON): cv.string,
})

SERVICE_ADD_UNAVAILABILITY_SCHEMA = vol.Schema({
    vol.Required(ATTR_START): cv.datetime,
    vol.Required(ATTR_END): cv.datetime,
})

SERVICE_REMOVE_UNAVAILABILITY_SCHEMA = vol.Schema({
    vol.Required(ATTR_WINDOW_ID): cv.string,
})


async def async_setup_services(hass: HomeAssistant) -> None:
    async def handle_create_project(call: ServiceCall) -> None:
        store: PrintAssistStore = hass.data[DOMAIN]["store"]
        coordinator: PrintAssistCoordinator = hass.data[DOMAIN]["coordinator"]
        name = call.data[ATTR_PROJECT_NAME]
        notes = call.data.get("notes", "")
        project = await store.async_create_project(name, notes)
        _LOGGER.info("Created project: %s (%s)", project.name, project.id)
        await coordinator.async_request_refresh()

    async def handle_delete_project(call: ServiceCall) -> None:
        store: PrintAssistStore = hass.data[DOMAIN]["store"]
        coordinator: PrintAssistCoordinator = hass.data[DOMAIN]["coordinator"]
        project_id = call.data[ATTR_PROJECT_ID]
        deleted = await store.async_delete_project(project_id)
        if deleted:
            _LOGGER.info("Deleted project: %s", project_id)
        coordinator.invalidate_schedule()
        await coordinator.async_request_refresh()

    async def handle_upload_3mf(call: ServiceCall) -> None:
        store: PrintAssistStore = hass.data[DOMAIN]["store"]
        file_handler: FileHandler = hass.data[DOMAIN]["file_handler"]
        coordinator: PrintAssistCoordinator = hass.data[DOMAIN]["coordinator"]

        project_id = call.data[ATTR_PROJECT_ID]
        filename = call.data[ATTR_FILENAME]
        file_b64 = call.data[ATTR_FILE_CONTENT]

        project = store.get_project(project_id)
        if not project:
            _LOGGER.error("Project not found: %s", project_id)
            return

        try:
            file_content = base64.b64decode(file_b64)
        except Exception as e:
            _LOGGER.error("Failed to decode file content: %s", e)
            return

        plates = await file_handler.process_file(file_content, project_id, filename)
        if plates:
            await store.async_add_plates(plates)
            _LOGGER.info("Uploaded %d plates from %s", len(plates), filename)
        coordinator.invalidate_schedule()
        await coordinator.async_request_refresh()

    async def handle_delete_plate(call: ServiceCall) -> None:
        store: PrintAssistStore = hass.data[DOMAIN]["store"]
        file_handler: FileHandler = hass.data[DOMAIN]["file_handler"]
        coordinator: PrintAssistCoordinator = hass.data[DOMAIN]["coordinator"]

        plate_id = call.data[ATTR_PLATE_ID]
        plate = store.get_plate(plate_id)
        if plate:
            await file_handler.delete_plate_files(plate)
            await store.async_delete_plate(plate_id)
            _LOGGER.info("Deleted plate: %s", plate_id)
        coordinator.invalidate_schedule()
        await coordinator.async_request_refresh()

    async def handle_set_priority(call: ServiceCall) -> None:
        store: PrintAssistStore = hass.data[DOMAIN]["store"]
        coordinator: PrintAssistCoordinator = hass.data[DOMAIN]["coordinator"]

        plate_id = call.data[ATTR_PLATE_ID]
        priority = call.data[ATTR_PRIORITY]
        await store.async_set_plate_priority(plate_id, priority)
        _LOGGER.info("Set priority for %s to %d", plate_id, priority)
        coordinator.invalidate_schedule()
        await coordinator.async_request_refresh()

    async def handle_set_quantity(call: ServiceCall) -> None:
        store: PrintAssistStore = hass.data[DOMAIN]["store"]
        coordinator: PrintAssistCoordinator = hass.data[DOMAIN]["coordinator"]

        plate_id = call.data[ATTR_PLATE_ID]
        quantity = call.data[ATTR_QUANTITY]
        await store.async_set_plate_quantity(plate_id, quantity)
        _LOGGER.info("Set quantity for %s to %d", plate_id, quantity)
        coordinator.invalidate_schedule()
        await coordinator.async_request_refresh()

    async def handle_start_job(call: ServiceCall) -> None:
        store: PrintAssistStore = hass.data[DOMAIN]["store"]
        coordinator: PrintAssistCoordinator = hass.data[DOMAIN]["coordinator"]

        job_id = call.data[ATTR_JOB_ID]
        if store.get_active_job():
            _LOGGER.warning("Cannot start job: another job is already printing")
            return

        success = await store.async_start_job(job_id)
        if success:
            _LOGGER.info("Started job: %s", job_id)
        coordinator.invalidate_schedule()
        await coordinator.async_request_refresh()

    async def handle_complete_job(call: ServiceCall) -> None:
        store: PrintAssistStore = hass.data[DOMAIN]["store"]
        coordinator: PrintAssistCoordinator = hass.data[DOMAIN]["coordinator"]

        job_id = call.data[ATTR_JOB_ID]
        success = await store.async_complete_job(job_id)
        if success:
            _LOGGER.info("Completed job: %s", job_id)
        coordinator.invalidate_schedule()
        await coordinator.async_request_refresh()

    async def handle_fail_job(call: ServiceCall) -> None:
        store: PrintAssistStore = hass.data[DOMAIN]["store"]
        coordinator: PrintAssistCoordinator = hass.data[DOMAIN]["coordinator"]

        job_id = call.data[ATTR_JOB_ID]
        reason = call.data.get(ATTR_FAILURE_REASON)
        new_job = await store.async_fail_job(job_id, reason)
        if new_job:
            _LOGGER.info("Failed job: %s (reason: %s), created replacement: %s", job_id, reason, new_job.id)
        coordinator.invalidate_schedule()
        await coordinator.async_request_refresh()

    async def handle_add_unavailability(call: ServiceCall) -> None:
        store: PrintAssistStore = hass.data[DOMAIN]["store"]
        coordinator: PrintAssistCoordinator = hass.data[DOMAIN]["coordinator"]

        start = call.data[ATTR_START]
        end = call.data[ATTR_END]
        await store.async_add_unavailability(start, end)
        _LOGGER.info("Added unavailability: %s to %s", start, end)
        coordinator.invalidate_schedule()
        await coordinator.async_request_refresh()

    async def handle_remove_unavailability(call: ServiceCall) -> None:
        store: PrintAssistStore = hass.data[DOMAIN]["store"]
        coordinator: PrintAssistCoordinator = hass.data[DOMAIN]["coordinator"]

        window_id = call.data[ATTR_WINDOW_ID]
        await store.async_remove_unavailability(window_id)
        _LOGGER.info("Removed unavailability: %s", window_id)
        coordinator.invalidate_schedule()
        await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN, SERVICE_CREATE_PROJECT, handle_create_project, SERVICE_CREATE_PROJECT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_PROJECT, handle_delete_project, SERVICE_DELETE_PROJECT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_UPLOAD_3MF, handle_upload_3mf, SERVICE_UPLOAD_3MF_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_PLATE, handle_delete_plate, SERVICE_DELETE_PLATE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_PLATE_PRIORITY, handle_set_priority, SERVICE_SET_PRIORITY_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_QUANTITY, handle_set_quantity, SERVICE_SET_QUANTITY_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_START_JOB, handle_start_job, SERVICE_START_JOB_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_COMPLETE_JOB, handle_complete_job, SERVICE_COMPLETE_JOB_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_FAIL_JOB, handle_fail_job, SERVICE_FAIL_JOB_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ADD_UNAVAILABILITY, handle_add_unavailability, SERVICE_ADD_UNAVAILABILITY_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_UNAVAILABILITY, handle_remove_unavailability, SERVICE_REMOVE_UNAVAILABILITY_SCHEMA
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    for service in [
        SERVICE_CREATE_PROJECT,
        SERVICE_DELETE_PROJECT,
        SERVICE_UPLOAD_3MF,
        SERVICE_DELETE_PLATE,
        SERVICE_SET_PLATE_PRIORITY,
        SERVICE_SET_QUANTITY,
        SERVICE_START_JOB,
        SERVICE_COMPLETE_JOB,
        SERVICE_FAIL_JOB,
        SERVICE_ADD_UNAVAILABILITY,
        SERVICE_REMOVE_UNAVAILABILITY,
    ]:
        hass.services.async_remove(DOMAIN, service)
