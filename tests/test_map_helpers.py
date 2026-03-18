from __future__ import annotations

import unittest

from core.pipeline import TrackResult
from core.track_model import TrackPoint, TrackSegment, TrackSummary
from gui.presentation import build_map_html, build_map_payload


class MapHelperTests(unittest.TestCase):
    def test_build_map_payload_includes_segments_start_end_and_invalid_points(self) -> None:
        points = [
            TrackPoint(time_str="000000.00", lat=10.0, lon=20.0, is_valid=True),
            TrackPoint(time_str="000001.00", lat=10.1, lon=20.1, is_valid=True),
            TrackPoint(
                time_str="000002.00",
                lat=10.2,
                lon=20.2,
                is_valid=False,
                invalid_reason="jump point",
            ),
            TrackPoint(time_str="000010.00", lat=10.3, lon=20.3, is_valid=True),
            TrackPoint(time_str="000011.00", lat=10.4, lon=20.4, is_valid=True),
        ]
        result = TrackResult(
            points=points,
            segments=[
                TrackSegment(points=points[:2]),
                TrackSegment(points=[points[2]]),
                TrackSegment(points=points[3:]),
            ],
            summary=TrackSummary(
                total_points=5,
                valid_points=4,
                invalid_points=1,
                segment_count=3,
                total_distance_m=1000.0,
                duration_seconds=20.0,
                max_speed_kmh=80.0,
                avg_speed_kmh=50.0,
            ),
        )

        payload = build_map_payload(result)

        self.assertEqual(len(payload["polylines"]), 2)
        self.assertEqual(payload["polylines"][0][0], [10.0, 20.0])
        self.assertEqual(payload["polylines"][1][-1], [10.4, 20.4])
        self.assertEqual(payload["start_point"]["time_str"], "000000.00")
        self.assertEqual(payload["end_point"]["time_str"], "000011.00")
        self.assertEqual(len(payload["invalid_points"]), 1)
        self.assertEqual(payload["invalid_points"][0]["reason"], "jump point")

    def test_build_map_html_contains_track_markers_and_empty_state(self) -> None:
        empty_html = build_map_html(None)
        self.assertIn("Open an NMEA file to view the track.", empty_html)

        result = TrackResult(
            points=[
                TrackPoint(time_str="000000.00", lat=1.0, lon=2.0, is_valid=True),
                TrackPoint(time_str="000001.00", lat=3.0, lon=4.0, is_valid=True),
            ],
            segments=[
                TrackSegment(
                    points=[
                        TrackPoint(time_str="000000.00", lat=1.0, lon=2.0, is_valid=True),
                        TrackPoint(time_str="000001.00", lat=3.0, lon=4.0, is_valid=True),
                    ]
                )
            ],
            summary=TrackSummary(
                total_points=2,
                valid_points=2,
                invalid_points=0,
                segment_count=1,
                total_distance_m=100.0,
                duration_seconds=1.0,
                max_speed_kmh=50.0,
                avg_speed_kmh=50.0,
            ),
        )

        html = build_map_html(result)

        self.assertIn("Start", html)
        self.assertIn("End", html)
        self.assertIn('"polylines":[[[1.0,2.0],[3.0,4.0]]]', html)

    def test_build_map_payload_can_color_track_by_speed_and_include_anomaly_points(self) -> None:
        points = [
            TrackPoint(time_str="000000.00", lat=0.0, lon=0.0, is_valid=True),
            TrackPoint(time_str="000010.00", lat=0.0, lon=0.001, is_valid=True, calculated_speed_kmh=40.0),
            TrackPoint(
                time_str="000011.00",
                lat=0.0,
                lon=0.003,
                is_valid=True,
                calculated_speed_kmh=800.0,
                anomaly_flags=["high_speed", "jump"],
            ),
        ]
        result = TrackResult(
            points=points,
            segments=[TrackSegment(points=points)],
            summary=TrackSummary(
                total_points=3,
                valid_points=3,
                invalid_points=0,
                segment_count=1,
                total_distance_m=0.0,
                duration_seconds=11.0,
                max_speed_kmh=800.0,
                avg_speed_kmh=100.0,
            ),
        )

        payload = build_map_payload(result, color_by_speed=True)

        self.assertTrue(payload["color_by_speed"])
        self.assertEqual(len(payload["speed_polylines"]), 2)
        self.assertNotEqual(
            payload["speed_polylines"][0]["color"],
            payload["speed_polylines"][1]["color"],
        )
        self.assertEqual(len(payload["anomaly_points"]), 1)
        self.assertEqual(payload["anomaly_points"][0]["reason"], "high_speed; jump")


if __name__ == "__main__":
    unittest.main()
