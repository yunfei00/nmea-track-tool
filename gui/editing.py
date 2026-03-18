from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from core.anomaly import detect_anomalies as detect_track_anomalies
from core.pipeline import TrackResult, build_track_from_points
from core.track_model import TrackPoint, clone_track_point

RecomputeTrackFn = Callable[..., TrackResult]


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


@dataclass
class TrackEditSession:
    original_points: list[TrackPoint]
    working_points: list[TrackPoint]
    file_path: Path | None = None
    max_speed_kmh: float = 300.0
    split_gap_seconds: float = 10.0
    current_result: TrackResult | None = None

    @classmethod
    def from_track_result(
        cls,
        result: TrackResult,
        *,
        file_path: str | Path | None = None,
        max_speed_kmh: float = 300.0,
        split_gap_seconds: float = 10.0,
    ) -> "TrackEditSession":
        original_points = clone_track_points(result.points)
        working_points = clone_track_points(result.points)
        return cls(
            original_points=original_points,
            working_points=working_points,
            file_path=Path(file_path) if file_path is not None else None,
            max_speed_kmh=max_speed_kmh,
            split_gap_seconds=split_gap_seconds,
            current_result=result,
        )

    @property
    def is_modified(self) -> bool:
        return self.working_points != self.original_points

    def delete_rows(
        self,
        selected_rows: Iterable[int],
        *,
        recompute_fn: RecomputeTrackFn = build_track_from_points,
    ) -> TrackResult:
        self.working_points = remove_points_by_rows(self.working_points, selected_rows)
        return self.recompute(recompute_fn=recompute_fn)

    def reset(
        self,
        *,
        recompute_fn: RecomputeTrackFn = build_track_from_points,
    ) -> TrackResult:
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

        self.working_points = remove_points_by_rows(self.working_points, anomaly_rows)
        return self.recompute(recompute_fn=recompute_fn)

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
