from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Iterable

from core.pipeline import TrackResult, build_track_from_points
from core.track_model import TrackPoint

RecomputeTrackFn = Callable[..., TrackResult]


def clone_track_points(points: Iterable[TrackPoint]) -> list[TrackPoint]:
    return [replace(point) for point in points]


def remove_points_by_rows(points: Iterable[TrackPoint], selected_rows: Iterable[int]) -> list[TrackPoint]:
    row_indexes = {row for row in selected_rows if row >= 0}
    return [replace(point) for index, point in enumerate(points) if index not in row_indexes]


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
