from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class NMEATrackCLITests(unittest.TestCase):
    def test_cli_analyze_basic_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "input.nmea"
            input_path.write_text(_sample_nmea_text(), encoding="ascii")

            completed = _run_cli(["analyze", str(input_path)])

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("NMEA Track Summary", completed.stdout)
        self.assertIn("Total points:", completed.stdout)
        self.assertIn("Valid points:", completed.stdout)

    def test_cli_summary_output_contains_expected_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "input.nmea"
            input_path.write_text(_sample_nmea_text(), encoding="ascii")

            completed = _run_cli(["analyze", str(input_path)])

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("Total points: 2", completed.stdout)
        self.assertIn("Valid points: 1", completed.stdout)
        self.assertIn("Invalid points: 1", completed.stdout)
        self.assertIn("Segment count:", completed.stdout)
        self.assertIn("Total distance (meters):", completed.stdout)
        self.assertIn("Duration (seconds):", completed.stdout)
        self.assertIn("Average speed (km/h):", completed.stdout)
        self.assertIn("Max speed (km/h):", completed.stdout)

    def test_cli_creates_export_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "input.nmea"
            points_csv_path = temp_path / "points.csv"
            summary_json_path = temp_path / "summary.json"
            input_path.write_text(_sample_nmea_text(), encoding="ascii")

            completed = _run_cli(
                [
                    "analyze",
                    str(input_path),
                    "--export-points-csv",
                    str(points_csv_path),
                    "--export-summary-json",
                    str(summary_json_path),
                ]
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertTrue(points_csv_path.is_file())
            self.assertTrue(summary_json_path.is_file())

            csv_text = points_csv_path.read_text(encoding="utf-8")
            summary_data = json.loads(summary_json_path.read_text(encoding="utf-8"))

        self.assertIn("time_str,lat,lon,alt_m", csv_text)
        self.assertIn("invalid_reason", csv_text)
        self.assertEqual(summary_data["total_points"], 2)
        self.assertEqual(summary_data["valid_points"], 1)
        self.assertEqual(summary_data["invalid_points"], 1)

    def test_cli_anomaly_summary_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "input.nmea"
            input_path.write_text(_sample_nmea_text(), encoding="ascii")

            completed = _run_cli(["analyze", str(input_path), "--detect-anomalies"])

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("Anomaly summary:", completed.stdout)
        self.assertIn("- total:", completed.stdout)
        self.assertIn("- speed:", completed.stdout)
        self.assertIn("- jump:", completed.stdout)
        self.assertIn("- time:", completed.stdout)


def _run_cli(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "cli.nmea_track_cli", *arguments],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _sample_nmea_text() -> str:
    return "\n".join(
        [
            "$GPRMC,000010.00,A,3954.3882,N,11622.0742,E,36.70,357.45,010170,,*0A",
            "$GPGGA,000010.00,3954.3882,N,11622.0742,E,1,08,1.0,54.0,M,0.0,M,,*68",
            "$GPRMC,000025.00,V,3954.3903,N,11622.0741,E,37.25,357.45,010170,,*11",
            "$GPGGA,000025.00,3954.3903,N,11622.0741,E,0,08,1.0,54.1,M,0.0,M,,*65",
        ]
    )


if __name__ == "__main__":
    unittest.main()
