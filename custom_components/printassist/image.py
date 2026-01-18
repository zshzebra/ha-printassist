"""Image entities for PrintAssist."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PrintAssistCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PrintAssistCoordinator = hass.data[DOMAIN]["coordinator"]

    async_add_entities([
        PrintAssistActiveJobImage(coordinator, hass),
        PrintAssistNextPrintImage(coordinator, hass),
    ])


class PrintAssistImageBase(CoordinatorEntity[PrintAssistCoordinator], ImageEntity):
    _attr_has_entity_name = True
    _attr_content_type = "image/png"

    def __init__(
        self,
        coordinator: PrintAssistCoordinator,
        hass: HomeAssistant,
        key: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        ImageEntity.__init__(self, hass)
        self._attr_unique_id = f"printassist_{key}"
        self._attr_name = name
        self._cached_path: str | None = None

    def _get_thumbnail_path(self) -> str | None:
        raise NotImplementedError

    def _get_file_path(self) -> Path | None:
        thumbnail_path = self._get_thumbnail_path()
        if not thumbnail_path:
            return None
        # /local/... maps to www/...
        if thumbnail_path.startswith("/local/"):
            relative = thumbnail_path[7:]  # strip "/local/"
            return Path(self.hass.config.path("www")) / relative
        return None

    @property
    def image_last_updated(self) -> datetime | None:
        thumbnail_path = self._get_thumbnail_path()
        if thumbnail_path != self._cached_path:
            self._cached_path = thumbnail_path
            self._attr_image_last_updated = datetime.now()
        return self._attr_image_last_updated

    async def async_image(self) -> bytes | None:
        file_path = self._get_file_path()
        if not file_path or not file_path.exists():
            return None
        return await self.hass.async_add_executor_job(file_path.read_bytes)


class PrintAssistActiveJobImage(PrintAssistImageBase):
    def __init__(self, coordinator: PrintAssistCoordinator, hass: HomeAssistant) -> None:
        super().__init__(coordinator, hass, "active_job_image", "Active Job Image")

    def _get_thumbnail_path(self) -> str | None:
        if not self.coordinator.data:
            return None
        active_plate = self.coordinator.data.get("active_plate")
        return active_plate.thumbnail_path if active_plate else None


class PrintAssistNextPrintImage(PrintAssistImageBase):
    def __init__(self, coordinator: PrintAssistCoordinator, hass: HomeAssistant) -> None:
        super().__init__(coordinator, hass, "next_print_image", "Next Print Image")

    def _get_thumbnail_path(self) -> str | None:
        if not self.coordinator.data:
            return None
        next_plate = self.coordinator.data.get("next_plate")
        return next_plate.thumbnail_path if next_plate else None
