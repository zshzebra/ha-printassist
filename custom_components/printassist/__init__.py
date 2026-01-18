"""PrintAssist - Home Assistant 3D Print Project Manager."""
from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

import voluptuous as vol
from aiohttp import web
from homeassistant.components import websocket_api
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.frontend import async_register_built_in_panel, async_remove_panel

from .const import DOMAIN, CONF_BAMBU_DEVICE_ID
from .coordinator import PrintAssistCoordinator
from .file_handler import FileHandler
from .printer_monitor import BambuPrinterMonitor
from .services import async_setup_services, async_unload_services
from .store import PrintAssistStore

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


@websocket_api.websocket_command({vol.Required("type"): "printassist/get_data"})
@callback
def ws_get_data(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    store: PrintAssistStore = hass.data[DOMAIN]["store"]
    coordinator: PrintAssistCoordinator = hass.data[DOMAIN]["coordinator"]

    projects = []
    for project in store.get_projects():
        completed, total = store.get_project_progress(project.id)
        projects.append({
            **asdict(project),
            "completed": completed,
            "total": total,
        })

    plates = [asdict(p) for p in store.get_plates()]
    jobs = [asdict(j) for j in store.get_jobs()]

    schedule = []
    computed_at = None
    next_breakpoint = None
    if coordinator.data:
        schedule = coordinator.data.get("schedule", [])
        computed_at = coordinator.data.get("computed_at")
        next_breakpoint = coordinator.data.get("next_breakpoint")

    connection.send_result(msg["id"], {
        "projects": projects,
        "plates": plates,
        "jobs": jobs,
        "schedule": schedule,
        "computed_at": computed_at,
        "next_breakpoint": next_breakpoint,
        "unavailability_windows": [asdict(w) for w in store.get_unavailability_windows()],
    })


class PrintAssistUploadView(HomeAssistantView):
    url = "/api/printassist/upload"
    name = "api:printassist:upload"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        hass = request.app["hass"]

        if DOMAIN not in hass.data:
            return web.json_response({"error": "PrintAssist not loaded"}, status=500)

        store: PrintAssistStore = hass.data[DOMAIN]["store"]
        file_handler: FileHandler = hass.data[DOMAIN]["file_handler"]
        coordinator: PrintAssistCoordinator = hass.data[DOMAIN]["coordinator"]

        try:
            reader = await request.multipart()

            project_id = None
            filename = None
            file_content = None

            async for field in reader:
                if field.name == "project_id":
                    project_id = (await field.read()).decode()
                elif field.name == "file":
                    filename = field.filename
                    file_content = await field.read()

            if not all([project_id, filename, file_content]):
                return web.json_response({"error": "Missing required fields"}, status=400)

            project = store.get_project(project_id)
            if not project:
                return web.json_response({"error": "Project not found"}, status=404)

            plates = await file_handler.process_file(file_content, project_id, filename)
            if not plates:
                return web.json_response({"error": "No plates found in file"}, status=400)

            await store.async_add_plates(plates)
            coordinator.invalidate_schedule()
            await coordinator.async_request_refresh()

            return web.json_response({
                "success": True,
                "plates": [asdict(p) for p in plates],
            })

        except Exception as e:
            _LOGGER.exception("Upload failed")
            return web.json_response({"error": str(e)}, status=500)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    store = PrintAssistStore(hass)
    await store.async_load()

    file_handler = FileHandler(hass)
    coordinator = PrintAssistCoordinator(hass, store)

    printer_monitor = None
    bambu_device_id = entry.data.get(CONF_BAMBU_DEVICE_ID)
    if bambu_device_id:
        printer_monitor = BambuPrinterMonitor(
            hass,
            bambu_device_id,
            store,
            on_schedule_change=coordinator.invalidate_schedule,
        )
        if await printer_monitor.async_setup():
            coordinator.set_printer_monitor(printer_monitor)
            _LOGGER.info("Bambu printer monitor active for device: %s", bambu_device_id)
        else:
            _LOGGER.warning("Failed to setup Bambu printer monitor")
            printer_monitor = None

    hass.data[DOMAIN] = {
        "store": store,
        "file_handler": file_handler,
        "coordinator": coordinator,
        "printer_monitor": printer_monitor,
        "entry": entry,
    }

    await coordinator.async_config_entry_first_refresh()
    await async_setup_services(hass)

    websocket_api.async_register_command(hass, ws_get_data)
    hass.http.register_view(PrintAssistUploadView())

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    www_path = Path(__file__).parent / "www"
    await hass.http.async_register_static_paths([
        StaticPathConfig(
            url_path="/printassist",
            path=str(www_path),
            cache_headers=False,
        ),
    ])

    if "printassist" in hass.data.get("frontend_panels", {}):
        async_remove_panel(hass, "printassist")

    async_register_built_in_panel(
        hass,
        "custom",
        sidebar_title="PrintAssist",
        sidebar_icon="mdi:printer-3d",
        frontend_url_path="printassist",
        config={"_panel_custom": {
            "name": "printassist-panel",
            "embed_iframe": False,
            "trust_external": False,
            "module_url": "/printassist/printassist-panel.js",
        }},
        require_admin=False,
    )

    _LOGGER.info("PrintAssist setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await async_unload_services(hass)

    printer_monitor = hass.data[DOMAIN].get("printer_monitor")
    if printer_monitor:
        await printer_monitor.async_unload()

    async_remove_panel(hass, "printassist")

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.pop(DOMAIN)
    return unload_ok
