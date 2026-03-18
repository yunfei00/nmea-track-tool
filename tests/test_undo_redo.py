from __future__ import annotations

import unittest

from core.pipeline import build_track_from_points
from core.track_model import TrackPoint
from gui.editing import TrackEditSession


def _build_session(
    points: list[TrackPoint],
    *,
    max_speed_kmh: float = 300.0,
    history_limit: int = 20,
) -> TrackEditSession:
    result = build_track_from_points(points, max_speed_kmh=max_speed_kmh)
    return TrackEditSession.from_track_result(
        result,
        file_path="sample.nmea",
        max_speed_kmh=max_speed_kmh,
        history_limit=history_limit,
    )


class UndoRedoTests(unittest.TestCase):
    def test_delete_operation_supports_undo_and_redo(self) -> None:
        session = _build_session(
            [
                TrackPoint(time_str="000000.00", lat=0.0, lon=0.0, status="A", fix_quality=1),
                TrackPoint(time_str="000001.00", lat=0.0, lon=0.001, status="A", fix_quality=1),
                TrackPoint(time_str="000002.00", lat=0.0, lon=0.002, status="A", fix_quality=1),
            ]
        )

        session.delete_rows([1])

        self.assertEqual(len(session.working_points), 2)
        self.assertTrue(session.can_undo)
        self.assertFalse(session.can_redo)

        undone = session.undo()

        self.assertEqual(undone.summary.total_points, 3)
        self.assertEqual(len(session.working_points), 3)
        self.assertFalse(session.can_undo)
        self.assertTrue(session.can_redo)

        redone = session.redo()

        self.assertEqual(redone.summary.total_points, 2)
        self.assertEqual(len(session.working_points), 2)
        self.assertTrue(session.can_undo)
        self.assertFalse(session.can_redo)

    def test_new_edit_clears_redo_history(self) -> None:
        session = _build_session(
            [
                TrackPoint(time_str="000000.00", lat=0.0, lon=0.0, status="A", fix_quality=1),
                TrackPoint(time_str="000001.00", lat=0.0, lon=0.001, status="A", fix_quality=1),
                TrackPoint(time_str="000002.00", lat=0.0, lon=0.002, status="A", fix_quality=1),
            ]
        )

        session.delete_rows([2])
        session.undo()

        self.assertTrue(session.can_redo)

        session.delete_rows([0])

        self.assertFalse(session.can_redo)
        self.assertTrue(session.can_undo)
        self.assertEqual(len(session.working_points), 2)
        self.assertEqual(session.working_points[0].time_str, "000001.00")

    def test_remove_anomalies_can_be_undone_with_flags_restored(self) -> None:
        session = _build_session(
            [
                TrackPoint(time_str="000000.00", lat=0.0, lon=0.0, status="A", fix_quality=1),
                TrackPoint(time_str="000001.00", lat=0.0, lon=0.001, status="A", fix_quality=1),
                TrackPoint(time_str="000011.00", lat=0.0, lon=0.0011, status="A", fix_quality=1),
            ],
            max_speed_kmh=1000.0,
        )
        session.detect_anomalies()

        removed = session.remove_all_anomalies()

        self.assertEqual(removed.summary.total_points, 2)
        self.assertEqual(session.anomaly_row_indexes(), [])

        restored = session.undo()

        self.assertEqual(restored.summary.total_points, 3)
        self.assertEqual(session.anomaly_row_indexes(), [1])
        self.assertIn("high_speed", restored.points[1].anomaly_flags)

    def test_reset_operation_supports_undo_and_redo(self) -> None:
        session = _build_session(
            [
                TrackPoint(time_str="000000.00", lat=0.0, lon=0.0, status="A", fix_quality=1),
                TrackPoint(time_str="000001.00", lat=0.0, lon=0.001, status="A", fix_quality=1),
                TrackPoint(time_str="000002.00", lat=0.0, lon=0.002, status="A", fix_quality=1),
            ]
        )
        session.delete_rows([1])

        reset_result = session.reset()

        self.assertEqual(reset_result.summary.total_points, 3)
        self.assertFalse(session.is_modified)

        undone = session.undo()

        self.assertEqual(undone.summary.total_points, 2)
        self.assertTrue(session.is_modified)

        redone = session.redo()

        self.assertEqual(redone.summary.total_points, 3)
        self.assertFalse(session.is_modified)

    def test_history_is_bounded(self) -> None:
        session = _build_session(
            [
                TrackPoint(time_str="000000.00", lat=0.0, lon=0.0, status="A", fix_quality=1),
                TrackPoint(time_str="000001.00", lat=0.0, lon=0.001, status="A", fix_quality=1),
                TrackPoint(time_str="000002.00", lat=0.0, lon=0.002, status="A", fix_quality=1),
                TrackPoint(time_str="000003.00", lat=0.0, lon=0.003, status="A", fix_quality=1),
            ],
            history_limit=2,
        )

        session.delete_rows([3])
        session.delete_rows([2])
        session.delete_rows([1])

        self.assertEqual(len(session.undo_stack), 2)
        self.assertEqual(len(session.working_points), 1)

        session.undo()
        self.assertEqual(len(session.working_points), 2)

        session.undo()
        self.assertEqual(len(session.working_points), 3)

        session.undo()
        self.assertEqual(len(session.working_points), 3)


if __name__ == "__main__":
    unittest.main()
