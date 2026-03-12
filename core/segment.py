from __future__ import annotations

from typing import Iterable

from core.track_model import TrackPoint, TrackSegment, time_str_to_seconds


def split_track_segments(
    points: Iterable[TrackPoint],
    split_gap_seconds: float = 10.0,
) -> list[TrackSegment]:
    segments: list[TrackSegment] = []
    current_segment_points: list[TrackPoint] = []
    previous_time_seconds: float | None = None

    for point in points:
        current_time_seconds = _time_seconds_or_none(point)

        if _is_jump_invalid_point(point):
            if current_segment_points:
                segments.append(TrackSegment(points=current_segment_points))
                current_segment_points = []
            segments.append(TrackSegment(points=[point]))
            previous_time_seconds = current_time_seconds
            continue

        if current_segment_points and _should_split(
            previous_time_seconds,
            current_time_seconds,
            split_gap_seconds,
        ):
            segments.append(TrackSegment(points=current_segment_points))
            current_segment_points = []

        current_segment_points.append(point)
        previous_time_seconds = current_time_seconds

    if current_segment_points:
        segments.append(TrackSegment(points=current_segment_points))

    return segments


def _should_split(
    previous_time_seconds: float | None,
    current_time_seconds: float | None,
    split_gap_seconds: float,
) -> bool:
    if previous_time_seconds is None or current_time_seconds is None:
        return False

    delta_seconds = current_time_seconds - previous_time_seconds
    if delta_seconds > split_gap_seconds:
        return True
    if delta_seconds < 0.0:
        return True
    return False


def _time_seconds_or_none(point: TrackPoint) -> float | None:
    try:
        return time_str_to_seconds(point.time_str)
    except ValueError:
        return None


def _is_jump_invalid_point(point: TrackPoint) -> bool:
    return (not point.is_valid) and "jump point" in point.invalid_reason.lower()
