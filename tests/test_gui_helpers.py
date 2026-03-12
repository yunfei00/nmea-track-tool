from __future__ import annotations

import unittest

from core.track_model import TrackPoint, TrackSummary
from gui.presentation import build_summary_rows, track_point_to_row_values


class GUIHelperTests(unittest.TestCase):
    def test_build_summary_rows_formats_expected_fields(self) -> None:
        summary = TrackSummary(
            total_points=10,
            valid_points=8,
            invalid_points=2,
            segment_count=3,
            total_distance_m=1234.567,
            duration_seconds=98.765,
            max_speed_kmh=56.789,
            avg_speed_kmh=45.678,
        )

        rows = build_summary_rows(summary)

        self.assertEqual(rows[0], ("Total points", "10"))
        self.assertIn(("Valid points", "8"), rows)
        self.assertIn(("Invalid points", "2"), rows)
        self.assertIn(("Total distance (meters)", "1234.57"), rows)
        self.assertIn(("Duration (seconds)", "98.77"), rows)
        self.assertIn(("Average speed (km/h)", "45.68"), rows)
        self.assertIn(("Max speed (km/h)", "56.79"), rows)

    def test_track_point_to_row_values_formats_invalid_row_fields(self) -> None:
        point = TrackPoint(
            time_str="123519.00",
            lat=48.1173,
            lon=11.5166667,
            alt_m=545.4,
            speed_knots=22.4,
            course_deg=84.4,
            fix_quality=1,
            num_sats=8,
            hdop=0.9,
            is_valid=False,
            invalid_reason="jump point",
        )

        row = track_point_to_row_values(point)

        self.assertEqual(row[0], "123519.00")
        self.assertEqual(row[1], "48.117300")
        self.assertEqual(row[2], "11.516667")
        self.assertEqual(row[3], "545.4")
        self.assertEqual(row[4], "22.40")
        self.assertEqual(row[5], "84.40")
        self.assertEqual(row[6], "1")
        self.assertEqual(row[7], "8")
        self.assertEqual(row[8], "0.9")
        self.assertEqual(row[9], "False")
        self.assertEqual(row[10], "jump point")


if __name__ == "__main__":
    unittest.main()
