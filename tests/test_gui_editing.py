from __future__ import annotations

import unittest

from core.pipeline import TrackResult, build_track_from_points
from core.track_model import TrackPoint, TrackSegment, TrackSummary
from gui.editing import (
    TrackEditSession,
    build_window_title,
    clone_track_points,
    remove_points_by_rows,
)


class GUIEditingTests(unittest.TestCase):
    def test_remove_points_by_rows_updates_working_dataset(self) -> None:
        points = [
            TrackPoint(time_str="000000.00", lat=0.0, lon=0.0),
            TrackPoint(time_str="000001.00", lat=0.0, lon=0.1),
            TrackPoint(time_str="000002.00", lat=0.0, lon=0.2),
        ]

        remaining = remove_points_by_rows(points, [1])

        self.assertEqual(len(remaining), 2)
        self.assertEqual(remaining[0].time_str, "000000.00")
        self.assertEqual(remaining[1].time_str, "000002.00")

    def test_reset_restores_original_dataset(self) -> None:
        result = build_track_from_points(
            [
                TrackPoint(time_str="000000.00", lat=0.0, lon=0.0, status="A", fix_quality=1),
                TrackPoint(time_str="000001.00", lat=0.0, lon=0.001, status="A", fix_quality=1),
                TrackPoint(time_str="000002.00", lat=0.0, lon=0.002, status="A", fix_quality=1),
            ]
        )
        session = TrackEditSession.from_track_result(result, file_path="sample.nmea")

        session.delete_rows([1])
        self.assertTrue(session.is_modified)

        reset_result = session.reset()

        self.assertFalse(session.is_modified)
        self.assertEqual(len(session.working_points), 3)
        self.assertEqual(reset_result.summary.total_points, 3)

    def test_recompute_path_is_triggered_after_deletion(self) -> None:
        result = build_track_from_points(
            [
                TrackPoint(time_str="000000.00", lat=0.0, lon=0.0, status="A", fix_quality=1),
                TrackPoint(time_str="000001.00", lat=0.0, lon=0.001, status="A", fix_quality=1),
            ]
        )
        session = TrackEditSession.from_track_result(result, file_path="sample.nmea")
        calls: list[int] = []

        def fake_recompute(points, *, max_speed_kmh, split_gap_seconds):
            calls.append(len(points))
            return TrackResult(
                points=clone_track_points(points),
                segments=[TrackSegment(points=clone_track_points(points))] if points else [],
                summary=TrackSummary(
                    total_points=len(points),
                    valid_points=len(points),
                    invalid_points=0,
                    segment_count=1 if points else 0,
                    total_distance_m=0.0,
                    duration_seconds=0.0,
                    max_speed_kmh=0.0,
                    avg_speed_kmh=0.0,
                ),
            )

        recomputed = session.delete_rows([0], recompute_fn=fake_recompute)

        self.assertEqual(calls, [1])
        self.assertEqual(recomputed.summary.total_points, 1)
        self.assertTrue(session.is_modified)

    def test_build_window_title_shows_modified_state(self) -> None:
        self.assertEqual(build_window_title(None, False), "NMEA Track Viewer")
        self.assertEqual(
            build_window_title("D:/tracks/sample.nmea", False),
            "NMEA Track Viewer - sample.nmea",
        )
        self.assertEqual(
            build_window_title("D:/tracks/sample.nmea", True),
            "NMEA Track Viewer - sample.nmea (modified)",
        )


if __name__ == "__main__":
    unittest.main()
