from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core.nmea_parser import parse_nmea_file


REPO_ROOT = Path(__file__).resolve().parents[1]


class GenerateTrackCLITests(unittest.TestCase):
    def test_generate_track_cli_creates_parseable_nmea_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "generated.nmea"

            completed = _run_generate_cli(
                [
                    "--start",
                    "39.9042,116.4074",
                    "--end",
                    "39.9142,116.4274",
                    "--output",
                    str(output_path),
                    "--routing-mode",
                    "mock",
                ]
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertTrue(output_path.is_file())
            points = parse_nmea_file(output_path)

        self.assertIn("Generated NMEA Track", completed.stdout)
        self.assertIn("Route provider: mock", completed.stdout)
        self.assertIn("Output file:", completed.stdout)
        self.assertGreaterEqual(len(points), 2)

    def test_generate_track_cli_writes_expected_start_and_end_points(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "generated.nmea"

            completed = _run_generate_cli(
                [
                    "--start",
                    "39.9042,116.4074",
                    "--end",
                    "39.9142,116.4274",
                    "--output",
                    str(output_path),
                    "--routing-mode",
                    "mock",
                    "--disable-traffic-lights",
                ]
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            points = parse_nmea_file(output_path)

        self.assertAlmostEqual(points[0].lat or 0.0, 39.9042, places=4)
        self.assertAlmostEqual(points[0].lon or 0.0, 116.4074, places=4)
        self.assertAlmostEqual(points[-1].lat or 0.0, 39.9142, places=4)
        self.assertAlmostEqual(points[-1].lon or 0.0, 116.4274, places=4)


def _run_generate_cli(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "cli.generate_track", *arguments],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


if __name__ == "__main__":
    unittest.main()
