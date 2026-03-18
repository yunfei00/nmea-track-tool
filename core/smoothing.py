from __future__ import annotations

from typing import List

from core.track_model import TrackPoint

DEFAULT_SMOOTHING_WINDOW = 5
MIN_SMOOTHING_WINDOW = 3
MAX_SMOOTHING_WINDOW = 7


def apply_moving_average(
    points: List[TrackPoint],
    window_size: int = DEFAULT_SMOOTHING_WINDOW,
) -> List[TrackPoint]:
    _validate_window_size(window_size)

    for point in points:
        point.clear_smoothed_coordinates()

    for index, point in enumerate(points):
        start_index, end_index = _window_bounds(index, len(points), window_size)
        window_points = points[start_index:end_index]
        usable_points = [candidate for candidate in window_points if _has_usable_coordinates(candidate)]
        if not usable_points:
            continue

        point.smoothed_lat = sum(candidate.lat for candidate in usable_points) / len(usable_points)
        point.smoothed_lon = sum(candidate.lon for candidate in usable_points) / len(usable_points)

    return points


def _window_bounds(index: int, point_count: int, window_size: int) -> tuple[int, int]:
    half_window = window_size // 2
    start_index = max(0, index - half_window)
    end_index = min(point_count, start_index + window_size)
    start_index = max(0, end_index - window_size)
    return start_index, end_index


def _validate_window_size(window_size: int) -> None:
    if MIN_SMOOTHING_WINDOW <= window_size <= MAX_SMOOTHING_WINDOW:
        return

    raise ValueError(
        f"window_size must be between {MIN_SMOOTHING_WINDOW} and {MAX_SMOOTHING_WINDOW}, "
        f"got {window_size}."
    )


def _has_usable_coordinates(point: TrackPoint) -> bool:
    return (
        point.lat is not None
        and point.lon is not None
        and -90.0 <= point.lat <= 90.0
        and -180.0 <= point.lon <= 180.0
    )
