from __future__ import annotations

import unittest

from core.pipeline import TrackResult, build_track_from_points
from core.smoothing import apply_moving_average
from core.track_model import TrackPoint, TrackSegment, TrackSummary
from gui.editing import TrackEditSession
from gui.presentation import build_map_payload, track_point_to_row_values


class SmoothingTests(unittest.TestCase):
    def test_apply_moving_average_keeps_raw_coordinates_and_sets_smoothed_values(self) -> None:
        points = [
            TrackPoint(time_str="000000.00", lat=10.0, lon=20.0),
            TrackPoint(time_str="000001.00", lat=11.0, lon=21.0),
            TrackPoint(time_str="000002.00", lat=15.0, lon=25.0),
            TrackPoint(time_str="000003.00", lat=11.0, lon=21.0),
            TrackPoint(time_str="000004.00", lat=10.0, lon=20.0),
        ]

        apply_moving_average(points, window_size=3)

        self.assertEqual(points[2].lat, 15.0)
        self.assertEqual(points[2].lon, 25.0)
        self.assertAlmostEqual(points[2].smoothed_lat, 37.0 / 3.0, places=6)
        self.assertAlmostEqual(points[2].smoothed_lon, 67.0 / 3.0, places=6)

    def test_track_point_to_row_values_can_show_raw_or_smoothed_coordinates(self) -> None:
        point = TrackPoint(
            time_str="123519.00",
            lat=48.1173,
            lon=11.5166667,
            smoothed_lat=48.1200,
            smoothed_lon=11.5200,
        )

        raw_row = track_point_to_row_values(point)
        smoothed_row = track_point_to_row_values(point, use_smoothed_coordinates=True)

        self.assertEqual(raw_row[1], "48.117300")
        self.assertEqual(raw_row[2], "11.516667")
        self.assertEqual(smoothed_row[1], "48.120000")
        self.assertEqual(smoothed_row[2], "11.520000")

    def test_build_map_payload_can_use_smoothed_coordinates(self) -> None:
        points = [
            TrackPoint(
                time_str="000000.00",
                lat=10.0,
                lon=20.0,
                smoothed_lat=10.01,
                smoothed_lon=20.01,
                is_valid=True,
            ),
            TrackPoint(
                time_str="000001.00",
                lat=10.1,
                lon=20.1,
                smoothed_lat=10.08,
                smoothed_lon=20.08,
                is_valid=True,
            ),
        ]
        result = TrackResult(
            points=points,
            segments=[TrackSegment(points=points)],
            summary=TrackSummary(
                total_points=2,
                valid_points=2,
                invalid_points=0,
                segment_count=1,
                total_distance_m=0.0,
                duration_seconds=1.0,
                max_speed_kmh=0.0,
                avg_speed_kmh=0.0,
            ),
        )

        raw_payload = build_map_payload(result)
        smoothed_payload = build_map_payload(result, use_smoothed_coordinates=True)

        self.assertEqual(raw_payload["polylines"][0][0], [10.0, 20.0])
        self.assertEqual(smoothed_payload["polylines"][0][0], [10.01, 20.01])
        self.assertEqual(smoothed_payload["end_point"]["lat"], 10.08)

    def test_track_edit_session_applies_smoothing_without_overwriting_working_points(self) -> None:
        result = build_track_from_points(
            [
                TrackPoint(time_str="000000.00", lat=10.0, lon=20.0, status="A", fix_quality=1),
                TrackPoint(time_str="000001.00", lat=11.0, lon=21.0, status="A", fix_quality=1),
                TrackPoint(time_str="000002.00", lat=15.0, lon=25.0, status="A", fix_quality=1),
            ]
        )
        session = TrackEditSession.from_track_result(result, file_path="sample.nmea")

        smoothed_result = session.apply_smoothing()

        self.assertTrue(session.has_smoothed_points)
        self.assertTrue(session.use_smoothed_view)
        self.assertIsNone(session.working_points[1].smoothed_lat)
        self.assertIsNotNone(smoothed_result.points[1].smoothed_lat)
        self.assertFalse(session.is_modified)


if __name__ == "__main__":
    unittest.main()
