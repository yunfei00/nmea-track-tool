from __future__ import annotations

from typing import List

from core.geo import calc_speed_kmh, haversine_m
from core.track_model import TrackPoint, time_str_to_seconds

HIGH_SPEED_THRESHOLD_KMH = 200.0
JUMP_DISTANCE_THRESHOLD_M = 200.0
JUMP_WINDOW_SECONDS = 1.0


def detect_anomalies(points: List[TrackPoint]) -> List[TrackPoint]:
    previous_point: TrackPoint | None = None
    previous_time_seconds: float | None = None

    for point in points:
        point.clear_anomaly_flags()

    for point in points:
        current_time_seconds = _time_seconds_or_none(point)

        if (
            previous_point is not None
            and previous_time_seconds is not None
            and current_time_seconds is not None
        ):
            delta_seconds = current_time_seconds - previous_time_seconds
            if delta_seconds <= 0.0:
                point.add_anomaly_flag("time_error")
            elif _has_usable_coordinates(previous_point) and _has_usable_coordinates(point):
                distance_m = haversine_m(
                    previous_point.lat,
                    previous_point.lon,
                    point.lat,
                    point.lon,
                )
                speed_kmh = calc_speed_kmh(distance_m, delta_seconds)

                if speed_kmh > HIGH_SPEED_THRESHOLD_KMH:
                    point.add_anomaly_flag("high_speed")

                if (
                    delta_seconds <= JUMP_WINDOW_SECONDS
                    and distance_m > JUMP_DISTANCE_THRESHOLD_M
                ):
                    point.add_anomaly_flag("jump")

        previous_point = point
        previous_time_seconds = current_time_seconds

    return points


def _time_seconds_or_none(point: TrackPoint) -> float | None:
    try:
        return time_str_to_seconds(point.time_str)
    except ValueError:
        return None


def _has_usable_coordinates(point: TrackPoint) -> bool:
    return (
        point.lat is not None
        and point.lon is not None
        and -90.0 <= point.lat <= 90.0
        and -180.0 <= point.lon <= 180.0
    )
