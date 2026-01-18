"""Tests for PrintAssist file handler."""

import pytest
from unittest.mock import patch
from pathlib import Path
import io
import zipfile

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])

from custom_components.printassist.file_handler import FileHandler


class TestGcodeTimeParsing:
    @pytest.fixture
    def file_handler(self, mock_hass):
        with patch("pathlib.Path.mkdir"):
            return FileHandler(mock_hass)

    def test_parse_bambu_time_format(self, file_handler):
        gcode = "; estimated printing time (normal mode) = 2h 30m 45s\nG28\n"
        result = file_handler._parse_time_from_gcode(gcode)
        assert result == 2 * 3600 + 30 * 60 + 45

    def test_parse_bambu_time_with_days(self, file_handler):
        gcode = "; estimated printing time (normal mode) = 1d 5h 30m 0s\nG28\n"
        result = file_handler._parse_time_from_gcode(gcode)
        assert result == 1 * 86400 + 5 * 3600 + 30 * 60

    def test_parse_time_seconds_only(self, file_handler):
        gcode = "; TIME:5400\nG28\n"
        result = file_handler._parse_time_from_gcode(gcode)
        assert result == 5400

    def test_parse_time_estimated_time(self, file_handler):
        gcode = "; estimated_time: 7200\nG28\n"
        result = file_handler._parse_time_from_gcode(gcode)
        assert result == 7200

    def test_parse_orcaslicer_model_time(self, file_handler):
        gcode = "; model printing time: 5h 53m 25s; total estimated time: 5h 59m 37s\nG28\n"
        result = file_handler._parse_time_from_gcode(gcode)
        assert result == 5 * 3600 + 53 * 60 + 25

    def test_parse_orcaslicer_total_time(self, file_handler):
        gcode = "; total estimated time: 2h 15m 30s\nG28\n"
        result = file_handler._parse_time_from_gcode(gcode)
        assert result == 2 * 3600 + 15 * 60 + 30

    def test_no_time_found(self, file_handler):
        gcode = "G28\nG1 X0 Y0\n"
        result = file_handler._parse_time_from_gcode(gcode)
        assert result == 0

    def test_parse_only_first_500_lines(self, file_handler):
        lines = ["; unrelated comment\n"] * 600
        lines[10] = "; TIME:3600\n"
        lines[550] = "; TIME:7200\n"
        gcode = "".join(lines)

        result = file_handler._parse_time_from_gcode(gcode)
        assert result == 3600


class TestThumbnailExtraction:
    @pytest.fixture
    def file_handler(self, mock_hass):
        with patch("pathlib.Path.mkdir"):
            return FileHandler(mock_hass)

    def test_extract_plate_thumbnail_standard_path(self, file_handler):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("Metadata/plate_1.png", b"PNG_DATA")

        buffer.seek(0)
        with zipfile.ZipFile(buffer) as zf:
            with patch.object(Path, "write_bytes"):
                result = file_handler._extract_plate_thumbnail(zf, 1, "test-id")

        assert result == "/local/printassist/thumbnails/test-id.png"

    def test_extract_plate_thumbnail_alt_path(self, file_handler):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr(".thumbnails/plate_1.png", b"PNG_DATA")

        buffer.seek(0)
        with zipfile.ZipFile(buffer) as zf:
            with patch.object(Path, "write_bytes"):
                result = file_handler._extract_plate_thumbnail(zf, 1, "test-id")

        assert result == "/local/printassist/thumbnails/test-id.png"

    def test_no_thumbnail_found(self, file_handler):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("model.stl", b"STL_DATA")

        buffer.seek(0)
        with zipfile.ZipFile(buffer) as zf:
            result = file_handler._extract_plate_thumbnail(zf, 1, "test-id")

        assert result is None


class TestFileProcessing:
    @pytest.fixture
    def file_handler(self, mock_hass):
        with patch("pathlib.Path.mkdir"):
            return FileHandler(mock_hass)

    @pytest.mark.asyncio
    async def test_process_gcode(self, file_handler):
        gcode = b"; TIME:3600\nG28\n"

        with patch.object(Path, "write_bytes"):
            plates = await file_handler.process_gcode(gcode, "proj-1", "test.gcode")

        assert len(plates) == 1
        assert plates[0].name == "test"
        assert plates[0].estimated_duration_seconds == 3600
        assert plates[0].plate_number == 1

    @pytest.mark.asyncio
    async def test_process_3mf_single_plate(self, file_handler):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("Metadata/plate_1.png", b"PNG")
            zf.writestr("Metadata/plate_1.gcode", b"; TIME:7200\nG28\n")

        with patch.object(Path, "write_bytes"):
            plates = await file_handler.process_3mf(buffer.getvalue(), "proj-1", "test.3mf")

        assert len(plates) == 1
        assert plates[0].plate_number == 1
        assert plates[0].estimated_duration_seconds == 7200
        assert plates[0].thumbnail_path is not None

    @pytest.mark.asyncio
    async def test_process_3mf_multi_plate(self, file_handler):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("Metadata/plate_1.gcode", b"; TIME:3600\nG28\n")
            zf.writestr("Metadata/plate_2.gcode", b"; TIME:7200\nG28\n")
            zf.writestr("Metadata/plate_1.png", b"PNG1")
            zf.writestr("Metadata/plate_2.png", b"PNG2")

        with patch.object(Path, "write_bytes"):
            plates = await file_handler.process_3mf(buffer.getvalue(), "proj-1", "test.3mf")

        assert len(plates) == 2
        plate_nums = {p.plate_number for p in plates}
        assert plate_nums == {1, 2}

    @pytest.mark.asyncio
    async def test_process_unsupported_file(self, file_handler):
        plates = await file_handler.process_file(b"data", "proj-1", "model.stl")
        assert plates == []


class TestReal3MFParsing:
    @pytest.fixture
    def file_handler(self, mock_hass):
        with patch("pathlib.Path.mkdir"):
            return FileHandler(mock_hass)

    @pytest.mark.asyncio
    async def test_process_real_orcaslicer_3mf(self, file_handler):
        fixture_path = Path(__file__).parent / "fixtures" / "sample.3mf"
        if not fixture_path.exists():
            pytest.skip("Fixture file not available")

        with open(fixture_path, "rb") as f:
            file_content = f.read()

        with patch.object(Path, "write_bytes"):
            plates = await file_handler.process_3mf(file_content, "orca-test", "sample.3mf")

        assert len(plates) >= 1
        assert plates[0].thumbnail_path is not None
        assert plates[0].estimated_duration_seconds == 5 * 3600 + 53 * 60 + 25
