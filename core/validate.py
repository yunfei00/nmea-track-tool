from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from core.geo import calc_speed_kmh, haversine_m
from core.track_model import TrackPoint, time_str_to_seconds

VALID_FIX_QUALITIES = {1, 2, 3, 4, 5, 6, 7, 8}


def validate_track_points(
    points: Iterable[TrackPoint],
    max_speed_kmh: float = 300.0,
) -> list[TrackPoint]:
    validated_points = [replace(point) for point in points]
    previous_reference_point: TrackPoint | None = None
    previous_reference_time: float | None = None

    for point in validated_points:
        point.is_valid = True
        point.invalid_reason = ""
        point.calculated_speed_kmh = None

        time_seconds = _parse_time_seconds(point)
        _apply_field_validations(point)

        if (
            previous_reference_point is not None
            and previous_reference_time is not None
            and time_seconds is not None
            and _has_usable_coordinates(previous_reference_point)
            and _has_usable_coordinates(point)
        ):
            delta_seconds = time_seconds - previous_reference_time
            if delta_seconds > 0.0:
                distance_m = haversine_m(
                    previous_reference_point.lat,
                    previous_reference_point.lon,
                    point.lat,
                    point.lon,
                )
                speed_kmh = calc_speed_kmh(distance_m, delta_seconds)
                point.calculated_speed_kmh = speed_kmh
                if point.is_valid and speed_kmh > max_speed_kmh:
                    point.set_invalid(
                        f"jump point: {speed_kmh:.1f} km/h exceeds {max_speed_kmh:.1f} km/h"
                    )

        if point.is_valid and time_seconds is not None and _has_usable_coordinates(point):
            previous_reference_point = point
            previous_reference_time = time_seconds

    return validated_points


def _apply_field_validations(point: TrackPoint) -> None:
    if point.lat is None or point.lon is None:
        point.set_invalid("missing lat/lon")
    else:
        if not -90.0 <= point.lat <= 90.0:
            point.set_invalid("latitude out of range")
        if not -180.0 <= point.lon <= 180.0:
            point.set_invalid("longitude out of range")

    if point.fix_quality is not None and point.fix_quality not in VALID_FIX_QUALITIES:
        point.set_invalid("invalid fix quality")

    if point.status and point.status.upper() != "A":
        point.set_invalid("invalid RMC status")


def _parse_time_seconds(point: TrackPoint) -> float | None:
    try:
        return time_str_to_seconds(point.time_str)
    except ValueError:
        point.set_invalid("invalid time_str")
        return None


def _has_usable_coordinates(point: TrackPoint) -> bool:
    return (
        point.lat is not None
        and point.lon is not None
        and -90.0 <= point.lat <= 90.0
        and -180.0 <= point.lon <= 180.0
    )
