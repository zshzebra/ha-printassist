"""File handling for 3MF and gcode files with multi-plate support."""
from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
import logging

from .store import Plate

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

GCODE_TIME_PATTERNS = [
    re.compile(r";\s*TIME:(\d+)", re.IGNORECASE),
    re.compile(r";\s*estimated_time[_:]?\s*(\d+)", re.IGNORECASE),
    re.compile(r";\s*print_time[_:]?\s*(\d+)", re.IGNORECASE),
]

TIME_HMS_PATTERN = re.compile(
    r";\s*(?:estimated printing time.*?[=:]|model printing time[=:]|total estimated time[=:])\s*"
    r"(?:(\d+)d\s*)?(?:(\d+)h\s*)?(?:(\d+)m\s*)?(?:(\d+)s)?",
    re.IGNORECASE,
)

PLATE_GCODE_PATTERN = re.compile(r"plate_(\d+)\.gcode", re.IGNORECASE)


@dataclass
class PlateInfo:
    plate_number: int
    name: str
    gcode_path: str
    estimated_duration_seconds: int
    thumbnail_path: str | None = None


class FileHandler:
    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._storage_path = Path(hass.config.path(".storage", "printassist", "files"))
        self._gcode_path = Path(hass.config.path(".storage", "printassist", "gcode"))
        self._thumbnail_path = Path(hass.config.path("www", "printassist", "thumbnails"))
        self._storage_path.mkdir(parents=True, exist_ok=True)
        self._gcode_path.mkdir(parents=True, exist_ok=True)
        self._thumbnail_path.mkdir(parents=True, exist_ok=True)

    def _parse_time_from_gcode(self, content: str) -> int:
        lines = content.split("\n")[:500]
        for line in lines:
            match = TIME_HMS_PATTERN.search(line)
            if match:
                days = int(match.group(1) or 0)
                hours = int(match.group(2) or 0)
                minutes = int(match.group(3) or 0)
                seconds = int(match.group(4) or 0)
                return days * 86400 + hours * 3600 + minutes * 60 + seconds

            for pattern in GCODE_TIME_PATTERNS:
                match = pattern.search(line)
                if match:
                    return int(match.group(1))
        return 0

    def _extract_plate_name(self, zf: zipfile.ZipFile, plate_num: int) -> str:
        json_path = f"Metadata/plate_{plate_num}.json"
        try:
            data = json.loads(zf.read(json_path).decode("utf-8"))
            if "bbox_objects" in data and data["bbox_objects"]:
                return data["bbox_objects"][0].get("name", f"Plate {plate_num}")
        except (KeyError, json.JSONDecodeError, UnicodeDecodeError):
            pass
        return f"Plate {plate_num}"

    def _extract_plate_thumbnail(
        self, zf: zipfile.ZipFile, plate_num: int, plate_id: str
    ) -> str | None:
        thumbnail_candidates = [
            f"Metadata/plate_{plate_num}.png",
            f".thumbnails/plate_{plate_num}.png",
        ]
        for thumbnail_path in thumbnail_candidates:
            try:
                thumbnail_data = zf.read(thumbnail_path)
                output_path = self._thumbnail_path / f"{plate_id}.png"
                output_path.write_bytes(thumbnail_data)
                return f"/local/printassist/thumbnails/{plate_id}.png"
            except KeyError:
                continue
        return None

    def _save_gcode(self, content: bytes, gcode_id: str) -> str:
        gcode_file = self._gcode_path / f"{gcode_id}.gcode"
        gcode_file.write_bytes(content)
        return gcode_id

    def _find_gcode_files(self, zf: zipfile.ZipFile) -> list[tuple[int, str]]:
        found: dict[int, str] = {}
        for name in zf.namelist():
            match = PLATE_GCODE_PATTERN.search(name)
            if match:
                plate_num = int(match.group(1))
                if plate_num not in found or name.startswith("Metadata/"):
                    found[plate_num] = name

        if not found:
            for name in zf.namelist():
                if name.endswith(".gcode"):
                    found[1] = name
                    break

        return sorted(found.items())

    async def process_3mf(
        self, file_content: bytes, project_id: str, filename: str
    ) -> list[Plate]:
        def _process() -> list[Plate]:
            plates: list[Plate] = []
            try:
                with zipfile.ZipFile(io.BytesIO(file_content)) as zf:
                    gcode_files = self._find_gcode_files(zf)

                    for plate_num, gcode_path in gcode_files:
                        gcode_id = f"{project_id}_{plate_num}"

                        try:
                            gcode_content = zf.read(gcode_path)
                        except KeyError:
                            _LOGGER.warning("Could not read gcode: %s", gcode_path)
                            continue

                        self._save_gcode(gcode_content, gcode_id)
                        estimated_time = self._parse_time_from_gcode(
                            gcode_content.decode("utf-8", errors="ignore")
                        )
                        plate_name = self._extract_plate_name(zf, plate_num)

                        plate = Plate.create(
                            project_id=project_id,
                            source_filename=filename,
                            plate_number=plate_num,
                            name=plate_name,
                            gcode_path=gcode_id,
                            estimated_duration_seconds=estimated_time,
                        )

                        thumbnail_url = self._extract_plate_thumbnail(zf, plate_num, plate.id)
                        if thumbnail_url:
                            plate.thumbnail_path = thumbnail_url

                        plates.append(plate)

            except zipfile.BadZipFile:
                _LOGGER.error("Invalid 3MF file: %s", filename)

            source_path = self._storage_path / filename
            source_path.write_bytes(file_content)

            return plates

        return await self._hass.async_add_executor_job(_process)

    async def process_gcode(
        self, file_content: bytes, project_id: str, filename: str
    ) -> list[Plate]:
        def _process() -> list[Plate]:
            gcode_id = f"{project_id}_1"
            self._save_gcode(file_content, gcode_id)

            content = file_content.decode("utf-8", errors="ignore")
            estimated_time = self._parse_time_from_gcode(content)

            name = Path(filename).stem
            plate = Plate.create(
                project_id=project_id,
                source_filename=filename,
                plate_number=1,
                name=name,
                gcode_path=gcode_id,
                estimated_duration_seconds=estimated_time,
            )
            return [plate]

        return await self._hass.async_add_executor_job(_process)

    async def process_file(
        self, file_content: bytes, project_id: str, filename: str
    ) -> list[Plate]:
        lower_name = filename.lower()
        if lower_name.endswith(".3mf"):
            return await self.process_3mf(file_content, project_id, filename)
        elif lower_name.endswith(".gcode"):
            return await self.process_gcode(file_content, project_id, filename)
        else:
            _LOGGER.warning("Unsupported file type: %s", filename)
            return []

    async def delete_plate_files(self, plate: Plate) -> None:
        def _delete() -> None:
            gcode_file = self._gcode_path / f"{plate.gcode_path}.gcode"
            if gcode_file.exists():
                gcode_file.unlink()
            if plate.thumbnail_path:
                thumbnail_file = self._thumbnail_path / f"{plate.id}.png"
                if thumbnail_file.exists():
                    thumbnail_file.unlink()

        await self._hass.async_add_executor_job(_delete)

    def get_gcode_path(self, gcode_id: str) -> Path:
        return self._gcode_path / f"{gcode_id}.gcode"
