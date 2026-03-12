from __future__ import annotations

import unittest

from core.geo import calc_speed_kmh, haversine_m, knots_to_kmh
from core.metrics import summarize_track
from core.nmea_parser import process_nmea_lines
from core.segment import split_track_segments
from core.track_model import TrackPoint
from core.validate import validate_track_points


class TrackProcessingCoreTests(unittest.TestCase):
    def test_geo_helpers_compute_distance_and_speed(self) -> None:
        distance_m = haversine_m(0.0, 0.0, 0.0, 0.001)

        self.assertAlmostEqual(distance_m, 111.19, places=1)
        self.assertAlmostEqual(knots_to_kmh(10.0), 18.52, places=2)
        self.assertAlmostEqual(calc_speed_kmh(1000.0, 100.0), 36.0, places=2)

    def test_validate_marks_invalid_latitude_and_longitude(self) -> None:
        points = [
            TrackPoint(time_str="000000.00", lat=91.0, lon=10.0),
            TrackPoint(time_str="000001.00", lat=10.0, lon=181.0),
            TrackPoint(time_str="000002.00", lat=None, lon=10.0),
        ]

        validated = validate_track_points(points)

        self.assertFalse(validated[0].is_valid)
        self.assertIn("latitude out of range", validated[0].invalid_reason.lower())
        self.assertFalse(validated[1].is_valid)
        self.assertIn("longitude out of range", validated[1].invalid_reason.lower())
        self.assertFalse(validated[2].is_valid)
        self.assertIn("missing lat/lon", validated[2].invalid_reason.lower())

    def test_validate_marks_jump_point_when_speed_is_too_high(self) -> None:
        points = [
            TrackPoint(time_str="000000.00", lat=0.0, lon=0.0, status="A", fix_quality=1),
            TrackPoint(time_str="000001.00", lat=0.0, lon=1.0, status="A", fix_quality=1),
        ]

        validated = validate_track_points(points, max_speed_kmh=300.0)

        self.assertTrue(validated[0].is_valid)
        self.assertFalse(validated[1].is_valid)
        self.assertIsNotNone(validated[1].calculated_speed_kmh)
        self.assertGreater(validated[1].calculated_speed_kmh, 300.0)
        self.assertIn("jump point", validated[1].invalid_reason.lower())

    def test_split_track_segments_on_time_gap(self) -> None:
        points = validate_track_points(
            [
                TrackPoint(time_str="000000.00", lat=0.0, lon=0.0, status="A", fix_quality=1),
                TrackPoint(time_str="000005.00", lat=0.0, lon=0.001, status="A", fix_quality=1),
                TrackPoint(time_str="000020.00", lat=0.0, lon=0.002, status="A", fix_quality=1),
            ]
        )

        segments = split_track_segments(points, split_gap_seconds=10.0)

        self.assertEqual(len(segments), 2)
        self.assertEqual(len(segments[0].points), 2)
        self.assertEqual(len(segments[1].points), 1)

    def test_summarize_track_counts_segments_distance_and_speeds(self) -> None:
        points = validate_track_points(
            [
                TrackPoint(time_str="000000.00", lat=0.0, lon=0.0, status="A", fix_quality=1),
                TrackPoint(time_str="000010.00", lat=0.0, lon=0.001, status="A", fix_quality=1),
                TrackPoint(time_str="000025.00", lat=0.0, lon=0.002, status="A", fix_quality=1),
                TrackPoint(time_str="000035.00", lat=0.0, lon=0.003, status="A", fix_quality=1),
            ]
        )
        segments = split_track_segments(points, split_gap_seconds=10.0)

        summary = summarize_track(points, segments)

        self.assertEqual(summary.total_points, 4)
        self.assertEqual(summary.valid_points, 4)
        self.assertEqual(summary.invalid_points, 0)
        self.assertEqual(summary.segment_count, 2)
        self.assertAlmostEqual(summary.total_distance_m, 222.39, places=1)
        self.assertAlmostEqual(summary.duration_seconds, 20.0, places=2)
        self.assertAlmostEqual(summary.max_speed_kmh, 40.03, places=2)
        self.assertAlmostEqual(summary.avg_speed_kmh, 40.03, places=2)

    def test_process_nmea_lines_runs_core_pipeline(self) -> None:
        lines = [
            "$GPRMC,000010.00,A,3954.3882,N,11622.0742,E,36.70,357.45,010170,,*0A",
            "$GPGGA,000010.00,3954.3882,N,11622.0742,E,1,08,1.0,54.0,M,0.0,M,,*68",
            "$GPRMC,000025.00,V,3954.3903,N,11622.0741,E,37.25,357.45,010170,,*11",
            "$GPGGA,000025.00,3954.3903,N,11622.0741,E,0,08,1.0,54.1,M,0.0,M,,*65",
        ]

        points, segments, summary = process_nmea_lines(lines)

        self.assertEqual(len(points), 2)
        self.assertEqual(summary.total_points, 2)
        self.assertEqual(summary.valid_points, 1)
        self.assertEqual(summary.invalid_points, 1)
        self.assertGreaterEqual(len(segments), 1)
        self.assertFalse(points[1].is_valid)
        self.assertIn("invalid rmc status", points[1].invalid_reason.lower())


if __name__ == "__main__":
    unittest.main()
