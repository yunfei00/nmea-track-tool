from __future__ import annotations

from typing import Iterable

from core.geo import calc_speed_kmh, haversine_m
from core.track_model import TrackPoint, TrackSegment, TrackSummary, time_str_to_seconds


def summarize_track(
    points: Iterable[TrackPoint],
    segments: Iterable[TrackSegment],
) -> TrackSummary:
    point_list = list(points)
    segment_list = list(segments)

    total_distance_m = 0.0
    duration_seconds = 0.0
    max_speed_kmh = 0.0

    for segment in segment_list:
        previous_valid_point: TrackPoint | None = None
        previous_valid_time: float | None = None

        for point in segment.points:
            current_time = _time_seconds_or_none(point)
            if (
                not point.is_valid
                or current_time is None
                or point.lat is None
                or point.lon is None
                or not -90.0 <= point.lat <= 90.0
                or not -180.0 <= point.lon <= 180.0
            ):
                previous_valid_point = None
                previous_valid_time = None
                continue

            if previous_valid_point is not None and previous_valid_time is not None:
                delta_seconds = current_time - previous_valid_time
                if delta_seconds > 0.0:
                    distance_m = haversine_m(
                        previous_valid_point.lat,
                        previous_valid_point.lon,
                        point.lat,
                        point.lon,
                    )
                    total_distance_m += distance_m
                    duration_seconds += delta_seconds
                    speed_kmh = point.calculated_speed_kmh
                    if speed_kmh is None:
                        speed_kmh = calc_speed_kmh(distance_m, delta_seconds)
                    if speed_kmh > max_speed_kmh:
                        max_speed_kmh = speed_kmh

            previous_valid_point = point
            previous_valid_time = current_time

    valid_points = sum(1 for point in point_list if point.is_valid)
    invalid_points = len(point_list) - valid_points
    avg_speed_kmh = (
        calc_speed_kmh(total_distance_m, duration_seconds)
        if duration_seconds > 0.0
        else 0.0
    )

    return TrackSummary(
        total_points=len(point_list),
        valid_points=valid_points,
        invalid_points=invalid_points,
        segment_count=len(segment_list),
        total_distance_m=total_distance_m,
        duration_seconds=duration_seconds,
        max_speed_kmh=max_speed_kmh,
        avg_speed_kmh=avg_speed_kmh,
    )


def _time_seconds_or_none(point: TrackPoint) -> float | None:
    try:
        return time_str_to_seconds(point.time_str)
    except ValueError:
        return None
