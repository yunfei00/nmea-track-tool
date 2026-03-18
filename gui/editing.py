from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Iterable

from core.anomaly import detect_anomalies as detect_track_anomalies
from core.pipeline import TrackResult, build_track_from_points
from core.track_model import TrackPoint, TrackSegment, clone_track_point

RecomputeTrackFn = Callable[..., TrackResult]
DEFAULT_HISTORY_LIMIT = 20


def clone_track_points(points: Iterable[TrackPoint]) -> list[TrackPoint]:
    return [clone_track_point(point) for point in points]


def remove_points_by_rows(points: Iterable[TrackPoint], selected_rows: Iterable[int]) -> list[TrackPoint]:
    row_indexes = {row for row in selected_rows if row >= 0}
    return [clone_track_point(point) for index, point in enumerate(points) if index not in row_indexes]


def build_window_title(file_path: str | Path | None, modified: bool) -> str:
    base_title = "NMEA Track Viewer"
    if not file_path:
        return base_title

    name = Path(file_path).name
    if modified:
        return f"{base_title} - {name} (modified)"
    return f"{base_title} - {name}"


@dataclass(slots=True)
class _SessionSnapshot:
    working_points: list[TrackPoint]
    current_result: TrackResult | None


@dataclass
class TrackEditSession:
    original_points: list[TrackPoint]
    working_points: list[TrackPoint]
    file_path: Path | None = None
    max_speed_kmh: float = 300.0
    split_gap_seconds: float = 10.0
    current_result: TrackResult | None = None
    history_limit: int = DEFAULT_HISTORY_LIMIT
    undo_stack: list[_SessionSnapshot] = field(default_factory=list)
    redo_stack: list[_SessionSnapshot] = field(default_factory=list)

    @classmethod
    def from_track_result(
        cls,
        result: TrackResult,
        *,
        file_path: str | Path | None = None,
        max_speed_kmh: float = 300.0,
        split_gap_seconds: float = 10.0,
        history_limit: int = DEFAULT_HISTORY_LIMIT,
    ) -> "TrackEditSession":
        original_points = clone_track_points(result.points)
        working_points = clone_track_points(result.points)
        return cls(
            original_points=original_points,
            working_points=working_points,
            file_path=Path(file_path) if file_path is not None else None,
            max_speed_kmh=max_speed_kmh,
            split_gap_seconds=split_gap_seconds,
            current_result=clone_track_result(result),
            history_limit=max(1, history_limit),
        )

    @property
    def is_modified(self) -> bool:
        return self.working_points != self.original_points

    @property
    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    def delete_rows(
        self,
        selected_rows: Iterable[int],
        *,
        recompute_fn: RecomputeTrackFn = build_track_from_points,
    ) -> TrackResult:
        updated_points = remove_points_by_rows(self.working_points, selected_rows)
        if len(updated_points) == len(self.working_points):
            if self.current_result is None:
                return self.recompute(recompute_fn=recompute_fn)
            return self.current_result

        self._push_undo_snapshot()
        self.working_points = updated_points
        return self.recompute(recompute_fn=recompute_fn)

    def reset(
        self,
        *,
        recompute_fn: RecomputeTrackFn = build_track_from_points,
    ) -> TrackResult:
        if self.working_points == self.original_points:
            if self.current_result is None:
                return self.recompute(recompute_fn=recompute_fn)
            return self.current_result

        self._push_undo_snapshot()
        self.working_points = clone_track_points(self.original_points)
        return self.recompute(recompute_fn=recompute_fn)

    def detect_anomalies(self) -> TrackResult:
        if self.current_result is None:
            return self.recompute()

        detect_track_anomalies(self.current_result.points)
        return self.current_result

    def anomaly_row_indexes(self) -> list[int]:
        if self.current_result is None:
            return []

        return [
            index
            for index, point in enumerate(self.current_result.points)
            if point.anomaly_flags
        ]

    def remove_all_anomalies(
        self,
        *,
        recompute_fn: RecomputeTrackFn = build_track_from_points,
    ) -> TrackResult:
        anomaly_rows = self.anomaly_row_indexes()
        if not anomaly_rows:
            if self.current_result is None:
                return self.recompute(recompute_fn=recompute_fn)
            return self.current_result

        self._push_undo_snapshot()
        self.working_points = remove_points_by_rows(self.working_points, anomaly_rows)
        return self.recompute(recompute_fn=recompute_fn)

    def undo(self) -> TrackResult:
        if not self.undo_stack:
            if self.current_result is None:
                return self.recompute()
            return self.current_result

        self._push_snapshot(self.redo_stack, self._snapshot_current_state())
        snapshot = self.undo_stack.pop()
        self._restore_snapshot(snapshot)
        if self.current_result is None:
            return self.recompute()
        return self.current_result

    def redo(self) -> TrackResult:
        if not self.redo_stack:
            if self.current_result is None:
                return self.recompute()
            return self.current_result

        self._push_snapshot(self.undo_stack, self._snapshot_current_state())
        snapshot = self.redo_stack.pop()
        self._restore_snapshot(snapshot)
        if self.current_result is None:
            return self.recompute()
        return self.current_result

    def recompute(
        self,
        *,
        recompute_fn: RecomputeTrackFn = build_track_from_points,
    ) -> TrackResult:
        self.current_result = recompute_fn(
            self.working_points,
            max_speed_kmh=self.max_speed_kmh,
            split_gap_seconds=self.split_gap_seconds,
        )
        self.working_points = clone_track_points(self.current_result.points)
        return self.current_result

    def _push_undo_snapshot(self) -> None:
        self._push_snapshot(self.undo_stack, self._snapshot_current_state())
        self.redo_stack.clear()

    def _snapshot_current_state(self) -> _SessionSnapshot:
        return _SessionSnapshot(
            working_points=clone_track_points(self.working_points),
            current_result=clone_track_result(self.current_result),
        )

    def _restore_snapshot(self, snapshot: _SessionSnapshot) -> None:
        self.working_points = clone_track_points(snapshot.working_points)
        self.current_result = clone_track_result(snapshot.current_result)

    def _push_snapshot(
        self,
        stack: list[_SessionSnapshot],
        snapshot: _SessionSnapshot,
    ) -> None:
        stack.append(snapshot)
        if len(stack) > self.history_limit:
            del stack[0]


def clone_track_result(result: TrackResult | None) -> TrackResult | None:
    if result is None:
        return None

    point_by_id: dict[int, TrackPoint] = {}
    cloned_points: list[TrackPoint] = []
    for point in result.points:
        cloned_point = point_by_id.get(id(point))
        if cloned_point is None:
            cloned_point = clone_track_point(point)
            point_by_id[id(point)] = cloned_point
        cloned_points.append(cloned_point)

    cloned_segments: list[TrackSegment] = []
    for segment in result.segments:
        cloned_segments.append(
            TrackSegment(
                points=[
                    _clone_track_point_with_cache(point, point_by_id)
                    for point in segment.points
                ]
            )
        )

    return TrackResult(
        points=cloned_points,
        segments=cloned_segments,
        summary=replace(result.summary),
    )


def _clone_track_point_with_cache(
    point: TrackPoint,
    point_by_id: dict[int, TrackPoint],
) -> TrackPoint:
    cloned_point = point_by_id.get(id(point))
    if cloned_point is not None:
        return cloned_point

    cloned_point = clone_track_point(point)
    point_by_id[id(point)] = cloned_point
    return cloned_point
