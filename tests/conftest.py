"""Pytest fixtures for PrintAssist tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.config.path = MagicMock(side_effect=lambda *args: "/".join(["/config"] + list(args)))
    hass.async_add_executor_job = AsyncMock(side_effect=lambda fn, *args: fn(*args))
    hass.data = {}
    hass.services = MagicMock()
    hass.services.async_register = MagicMock()
    hass.services.async_remove = MagicMock()
    return hass


@pytest.fixture
def mock_store_data():
    """Sample store data for testing."""
    return {
        "projects": [
            {
                "id": "proj-1",
                "name": "Test Project",
                "created_at": "2024-01-15T10:00:00",
                "notes": "",
            }
        ],
        "parts": [
            {
                "id": "part-1",
                "project_id": "proj-1",
                "name": "Benchy",
                "filename": "benchy.3mf",
                "thumbnail_path": "/local/printassist/thumbnails/part-1.png",
                "estimated_duration_seconds": 3600,
                "filament_type": None,
                "status": "pending",
                "priority": 0,
            },
            {
                "id": "part-2",
                "project_id": "proj-1",
                "name": "Calibration Cube",
                "filename": "cube.gcode",
                "thumbnail_path": None,
                "estimated_duration_seconds": 1800,
                "filament_type": None,
                "status": "pending",
                "priority": 5,
            },
        ],
        "jobs": [],
        "unavailability_windows": [],
    }


@pytest.fixture
def sample_gcode_content():
    """Sample gcode content with time estimate."""
    return """; Bambu Studio
; estimated printing time (normal mode) = 1h 30m 45s
; filament used [mm] = 5000.00
; filament used [g] = 15.00
G28 ; Home
G1 X0 Y0 Z5 F3000
"""


@pytest.fixture
def sample_unavailability_windows():
    """Sample unavailability windows for scheduler tests."""
    return [
        {"id": "w1", "start": "2024-01-15T22:00:00", "end": "2024-01-16T07:00:00"},
        {"id": "w2", "start": "2024-01-16T09:00:00", "end": "2024-01-16T17:00:00"},
    ]
