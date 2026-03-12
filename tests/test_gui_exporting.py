from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.pipeline import build_track_from_points
from core.track_model import TrackPoint
from gui.exporting import export_cleaned_nmea, export_points_csv, export_summary_json


class GUIExportingTests(unittest.TestCase):
    def test_export_points_csv_writes_current_working_points(self) -> None:
        result = build_track_from_points(
            [
                TrackPoint(time_str="000000.00", lat=0.0, lon=0.0, status="A", fix_quality=1),
                TrackPoint(time_str="000001.00", lat=0.0, lon=0.001, status="A", fix_quality=1),
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "points.csv"
            export_points_csv(result, output_path)
            csv_text = output_path.read_text(encoding="utf-8")

        self.assertIn("time_str,lat,lon,alt_m", csv_text)
        self.assertIn("000000.00", csv_text)
        self.assertIn("000001.00", csv_text)

    def test_export_summary_json_writes_summary_fields(self) -> None:
        result = build_track_from_points(
            [
                TrackPoint(time_str="000000.00", lat=0.0, lon=0.0, status="A", fix_quality=1),
                TrackPoint(time_str="000001.00", lat=0.0, lon=0.001, status="A", fix_quality=1),
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "summary.json"
            export_summary_json(result, output_path)
            summary = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(summary["total_points"], 2)
        self.assertIn("valid_points", summary)
        self.assertIn("total_distance_m", summary)

    def test_export_cleaned_nmea_writes_current_working_dataset(self) -> None:
        result = build_track_from_points(
            [
                TrackPoint(time_str="000000.00", lat=0.0, lon=0.0, status="A", fix_quality=1),
                TrackPoint(time_str="000001.00", lat=0.0, lon=0.001, status="V", fix_quality=0),
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "cleaned.nmea"
            line_count = export_cleaned_nmea(result, output_path)
            lines = output_path.read_text(encoding="ascii").splitlines()

        self.assertEqual(line_count, 4)
        self.assertEqual(len(lines), 4)
        self.assertTrue(lines[0].startswith("$GPRMC,000000.00,A,"))
        self.assertTrue(lines[2].startswith("$GPRMC,000001.00,V,"))

    def test_export_cleaned_nmea_rejects_non_writable_points(self) -> None:
        result = build_track_from_points(
            [
                TrackPoint(time_str="000000.00", lat=0.0, lon=0.0, status="A", fix_quality=1),
                TrackPoint(time_str="000001.00", lat=None, lon=0.001, status="A", fix_quality=1),
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "cleaned.nmea"
            with self.assertRaises(ValueError):
                export_cleaned_nmea(result, output_path)


if __name__ == "__main__":
    unittest.main()
