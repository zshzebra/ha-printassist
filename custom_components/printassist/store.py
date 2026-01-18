"""Persistent storage for PrintAssist."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.helpers.storage import Store

from .const import (
    STORAGE_KEY,
    STORAGE_VERSION,
    JOB_STATUS_QUEUED,
    JOB_STATUS_PRINTING,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@dataclass
class Project:
    id: str
    name: str
    created_at: str
    notes: str = ""

    @classmethod
    def create(cls, name: str, notes: str = "") -> Project:
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            created_at=datetime.now().isoformat(),
            notes=notes,
        )


@dataclass
class Plate:
    id: str
    project_id: str
    source_filename: str
    plate_number: int
    name: str
    gcode_path: str
    estimated_duration_seconds: int
    thumbnail_path: str | None = None
    quantity_needed: int = 1
    priority: int = 0

    @classmethod
    def create(
        cls,
        project_id: str,
        source_filename: str,
        plate_number: int,
        name: str,
        gcode_path: str,
        estimated_duration_seconds: int,
        thumbnail_path: str | None = None,
    ) -> Plate:
        return cls(
            id=str(uuid.uuid4()),
            project_id=project_id,
            source_filename=source_filename,
            plate_number=plate_number,
            name=name,
            gcode_path=gcode_path,
            estimated_duration_seconds=estimated_duration_seconds,
            thumbnail_path=thumbnail_path,
        )


@dataclass
class Job:
    id: str
    plate_id: str
    status: str
    created_at: str
    started_at: str | None = None
    ended_at: str | None = None
    failure_reason: str | None = None

    @classmethod
    def create(cls, plate_id: str) -> Job:
        return cls(
            id=str(uuid.uuid4()),
            plate_id=plate_id,
            status=JOB_STATUS_QUEUED,
            created_at=datetime.now().isoformat(),
        )


@dataclass
class UnavailabilityWindow:
    id: str
    start: str
    end: str

    @classmethod
    def create(cls, start: datetime, end: datetime) -> UnavailabilityWindow:
        return cls(
            id=str(uuid.uuid4()),
            start=start.isoformat(),
            end=end.isoformat(),
        )


@dataclass
class StoreData:
    projects: list[dict] = field(default_factory=list)
    plates: list[dict] = field(default_factory=list)
    jobs: list[dict] = field(default_factory=list)
    unavailability_windows: list[dict] = field(default_factory=list)


class PrintAssistStore:
    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: StoreData = StoreData()

    async def async_load(self) -> None:
        stored = await self._store.async_load()
        if stored:
            self._data = StoreData(
                projects=stored.get("projects", []),
                plates=stored.get("plates", []),
                jobs=stored.get("jobs", []),
                unavailability_windows=stored.get("unavailability_windows", []),
            )

    async def _async_save(self) -> None:
        await self._store.async_save(asdict(self._data))

    def get_projects(self) -> list[Project]:
        return [Project(**p) for p in self._data.projects]

    def get_project(self, project_id: str) -> Project | None:
        for p in self._data.projects:
            if p["id"] == project_id:
                return Project(**p)
        return None

    async def async_create_project(self, name: str, notes: str = "") -> Project:
        project = Project.create(name, notes)
        self._data.projects.append(asdict(project))
        await self._async_save()
        return project

    async def async_delete_project(self, project_id: str) -> bool:
        plate_ids = [p["id"] for p in self._data.plates if p["project_id"] == project_id]
        self._data.jobs = [j for j in self._data.jobs if j["plate_id"] not in plate_ids]
        self._data.plates = [p for p in self._data.plates if p["project_id"] != project_id]
        original_len = len(self._data.projects)
        self._data.projects = [p for p in self._data.projects if p["id"] != project_id]
        if len(self._data.projects) < original_len:
            await self._async_save()
            return True
        return False

    def get_plates(self, project_id: str | None = None) -> list[Plate]:
        plates = self._data.plates
        if project_id:
            plates = [p for p in plates if p["project_id"] == project_id]
        return [Plate(**p) for p in plates]

    def get_plate(self, plate_id: str) -> Plate | None:
        for p in self._data.plates:
            if p["id"] == plate_id:
                return Plate(**p)
        return None

    async def async_add_plates(self, plates: list[Plate]) -> None:
        for plate in plates:
            self._data.plates.append(asdict(plate))
            for _ in range(plate.quantity_needed):
                job = Job.create(plate.id)
                self._data.jobs.append(asdict(job))
        await self._async_save()

    async def async_delete_plate(self, plate_id: str) -> bool:
        self._data.jobs = [j for j in self._data.jobs if j["plate_id"] != plate_id]
        original_len = len(self._data.plates)
        self._data.plates = [p for p in self._data.plates if p["id"] != plate_id]
        if len(self._data.plates) < original_len:
            await self._async_save()
            return True
        return False

    async def async_set_plate_priority(self, plate_id: str, priority: int) -> bool:
        for p in self._data.plates:
            if p["id"] == plate_id:
                p["priority"] = priority
                await self._async_save()
                return True
        return False

    async def async_set_plate_quantity(self, plate_id: str, quantity: int) -> bool:
        plate = self.get_plate(plate_id)
        if not plate:
            return False

        current_queued = len([
            j for j in self._data.jobs
            if j["plate_id"] == plate_id and j["status"] == JOB_STATUS_QUEUED
        ])
        completed = len([
            j for j in self._data.jobs
            if j["plate_id"] == plate_id and j["status"] == JOB_STATUS_COMPLETED
        ])
        needed_queued = max(0, quantity - completed)
        delta = needed_queued - current_queued

        if delta > 0:
            for _ in range(delta):
                job = Job.create(plate_id)
                self._data.jobs.append(asdict(job))
        elif delta < 0:
            removed = 0
            new_jobs = []
            for j in self._data.jobs:
                if j["plate_id"] == plate_id and j["status"] == JOB_STATUS_QUEUED and removed < abs(delta):
                    removed += 1
                    continue
                new_jobs.append(j)
            self._data.jobs = new_jobs

        for p in self._data.plates:
            if p["id"] == plate_id:
                p["quantity_needed"] = quantity
                break

        await self._async_save()
        return True

    def get_jobs(self, plate_id: str | None = None, status: str | None = None) -> list[Job]:
        jobs = self._data.jobs
        if plate_id:
            jobs = [j for j in jobs if j["plate_id"] == plate_id]
        if status:
            jobs = [j for j in jobs if j["status"] == status]
        return [Job(**j) for j in jobs]

    def get_job(self, job_id: str) -> Job | None:
        for j in self._data.jobs:
            if j["id"] == job_id:
                return Job(**j)
        return None

    def get_queued_jobs(self) -> list[Job]:
        return self.get_jobs(status=JOB_STATUS_QUEUED)

    def get_active_job(self) -> Job | None:
        jobs = self.get_jobs(status=JOB_STATUS_PRINTING)
        return jobs[0] if jobs else None

    async def async_start_job(self, job_id: str) -> bool:
        for j in self._data.jobs:
            if j["id"] == job_id and j["status"] == JOB_STATUS_QUEUED:
                j["status"] = JOB_STATUS_PRINTING
                j["started_at"] = datetime.now().isoformat()
                await self._async_save()
                return True
        return False

    async def async_complete_job(self, job_id: str) -> bool:
        for j in self._data.jobs:
            if j["id"] == job_id and j["status"] == JOB_STATUS_PRINTING:
                j["status"] = JOB_STATUS_COMPLETED
                j["ended_at"] = datetime.now().isoformat()
                await self._async_save()
                return True
        return False

    async def async_fail_job(self, job_id: str, reason: str | None = None) -> Job | None:
        for j in self._data.jobs:
            if j["id"] == job_id and j["status"] == JOB_STATUS_PRINTING:
                j["status"] = JOB_STATUS_FAILED
                j["ended_at"] = datetime.now().isoformat()
                j["failure_reason"] = reason
                new_job = Job.create(j["plate_id"])
                self._data.jobs.append(asdict(new_job))
                await self._async_save()
                return new_job
        return None

    def get_project_progress(self, project_id: str) -> tuple[int, int]:
        plates = self.get_plates(project_id)
        plate_ids = {p.id for p in plates}
        completed = len([
            j for j in self._data.jobs
            if j["plate_id"] in plate_ids and j["status"] == JOB_STATUS_COMPLETED
        ])
        total = sum(p.quantity_needed for p in plates)
        return completed, total

    def get_unavailability_windows(self) -> list[UnavailabilityWindow]:
        return [UnavailabilityWindow(**w) for w in self._data.unavailability_windows]

    async def async_add_unavailability(self, start: datetime, end: datetime) -> UnavailabilityWindow:
        window = UnavailabilityWindow.create(start, end)
        self._data.unavailability_windows.append(asdict(window))
        await self._async_save()
        return window

    async def async_remove_unavailability(self, window_id: str) -> bool:
        original_len = len(self._data.unavailability_windows)
        self._data.unavailability_windows = [
            w for w in self._data.unavailability_windows if w["id"] != window_id
        ]
        if len(self._data.unavailability_windows) < original_len:
            await self._async_save()
            return True
        return False

    def to_dict(self) -> dict:
        return {
            "projects": self._data.projects,
            "plates": self._data.plates,
            "jobs": self._data.jobs,
            "unavailability_windows": self._data.unavailability_windows,
        }
