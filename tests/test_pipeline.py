from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.pipeline import TrackResult, build_track_from_file, build_track_from_lines


class PipelineTests(unittest.TestCase):
    def test_build_track_from_lines_returns_track_result(self) -> None:
        lines = [
            "$GPRMC,000010.00,A,3954.3882,N,11622.0742,E,36.70,357.45,010170,,*0A",
            "$GPGGA,000010.00,3954.3882,N,11622.0742,E,1,08,1.0,54.0,M,0.0,M,,*68",
            "$GPRMC,000025.00,V,3954.3903,N,11622.0741,E,37.25,357.45,010170,,*11",
            "$GPGGA,000025.00,3954.3903,N,11622.0741,E,0,08,1.0,54.1,M,0.0,M,,*65",
        ]

        result = build_track_from_lines(lines)

        self.assertIsInstance(result, TrackResult)
        self.assertEqual(len(result.points), 2)
        self.assertEqual(len(result.segments), 2)
        self.assertEqual(result.summary.total_points, 2)
        self.assertEqual(result.summary.valid_points, 1)
        self.assertEqual(result.summary.invalid_points, 1)
        self.assertFalse(result.points[1].is_valid)

    def test_build_track_from_file_returns_track_result(self) -> None:
        content = "\n".join(
            [
                "$GPRMC,000010.00,A,3954.3882,N,11622.0742,E,36.70,357.45,010170,,*0A",
                "$GPGGA,000010.00,3954.3882,N,11622.0742,E,1,08,1.0,54.0,M,0.0,M,,*68",
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "sample.nmea"
            input_path.write_text(content, encoding="ascii")

            result = build_track_from_file(input_path)

        self.assertIsInstance(result, TrackResult)
        self.assertEqual(len(result.points), 1)
        self.assertEqual(len(result.segments), 1)
        self.assertEqual(result.summary.total_points, 1)
        self.assertEqual(result.summary.valid_points, 1)
        self.assertEqual(result.summary.invalid_points, 0)


if __name__ == "__main__":
    unittest.main()
