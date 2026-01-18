"""Buttons for PrintAssist."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PrintAssistCoordinator
from .printer_monitor import BambuPrinterMonitor
from .store import PrintAssistStore


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PrintAssistCoordinator = hass.data[DOMAIN]["coordinator"]
    store: PrintAssistStore = hass.data[DOMAIN]["store"]
    printer_monitor: BambuPrinterMonitor | None = hass.data[DOMAIN].get("printer_monitor")

    async_add_entities([
        PrintAssistMarkSuccessButton(coordinator, store, printer_monitor),
        PrintAssistMarkFailedButton(coordinator, store, printer_monitor),
        PrintAssistRescheduleButton(coordinator),
    ])


class PrintAssistButtonBase(CoordinatorEntity[PrintAssistCoordinator], ButtonEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PrintAssistCoordinator,
        key: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"printassist_{key}"
        self._attr_name = name


class PrintAssistMarkSuccessButton(PrintAssistButtonBase):
    def __init__(
        self,
        coordinator: PrintAssistCoordinator,
        store: PrintAssistStore,
        printer_monitor: BambuPrinterMonitor | None,
    ) -> None:
        super().__init__(coordinator, "mark_success", "Mark Success")
        self._store = store
        self._printer_monitor = printer_monitor
        self._attr_icon = "mdi:check-circle"

    @property
    def available(self) -> bool:
        active_job = self._store.get_active_job()
        if not active_job:
            return False
        if self._printer_monitor and self._printer_monitor.is_printing():
            return False
        return True

    async def async_press(self) -> None:
        active_job = self._store.get_active_job()
        if active_job:
            await self._store.async_complete_job(active_job.id)
            self.coordinator.invalidate_schedule()
            await self.coordinator.async_request_refresh()


class PrintAssistMarkFailedButton(PrintAssistButtonBase):
    def __init__(
        self,
        coordinator: PrintAssistCoordinator,
        store: PrintAssistStore,
        printer_monitor: BambuPrinterMonitor | None,
    ) -> None:
        super().__init__(coordinator, "mark_failed", "Mark Failed")
        self._store = store
        self._printer_monitor = printer_monitor
        self._attr_icon = "mdi:close-circle"

    @property
    def available(self) -> bool:
        active_job = self._store.get_active_job()
        if not active_job:
            return False
        if self._printer_monitor and self._printer_monitor.is_printing():
            return False
        return True

    async def async_press(self) -> None:
        active_job = self._store.get_active_job()
        if active_job:
            await self._store.async_fail_job(active_job.id)
            self.coordinator.invalidate_schedule()
            await self.coordinator.async_request_refresh()


class PrintAssistRescheduleButton(PrintAssistButtonBase):
    def __init__(self, coordinator: PrintAssistCoordinator) -> None:
        super().__init__(coordinator, "reschedule", "Reschedule")
        self._attr_icon = "mdi:calendar-refresh"

    async def async_press(self) -> None:
        self.coordinator.invalidate_schedule()
        await self.coordinator.async_request_refresh()
