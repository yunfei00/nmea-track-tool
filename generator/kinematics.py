from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from core.geo import haversine_m
from generator.models import GeneratedTrackPoint, RouteNode, RoutePath

DISTANCE_EPSILON_M = 1e-6


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    if math.isclose(lat1, lat2, abs_tol=1e-12) and math.isclose(lon1, lon2, abs_tol=1e-12):
        return 0.0

    latitude1 = math.radians(lat1)
    longitude1 = math.radians(lon1)
    latitude2 = math.radians(lat2)
    longitude2 = math.radians(lon2)

    delta_lon = longitude2 - longitude1
    y = math.sin(delta_lon) * math.cos(latitude2)
    x = (
        math.cos(latitude1) * math.sin(latitude2)
        - math.sin(latitude1) * math.cos(latitude2) * math.cos(delta_lon)
    )
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def route_path_length_m(route_path: RoutePath) -> float:
    return sum(
        haversine_m(first.lat, first.lon, second.lat, second.lon)
        for first, second in zip(route_path.nodes, route_path.nodes[1:])
    )


def interpolate_route_path(
    route_path: RoutePath,
    *,
    sample_rate_hz: float = 1.0,
    target_speed_mps: float = 13.89,
    start_time: datetime | None = None,
) -> list[GeneratedTrackPoint]:
    if sample_rate_hz <= 0.0:
        raise ValueError("sample_rate_hz must be greater than zero.")
    if target_speed_mps <= 0.0:
        raise ValueError("target_speed_mps must be greater than zero.")

    segment_lengths = _segment_lengths(route_path.nodes)
    total_distance_m = sum(segment_lengths)
    normalized_start_time = _normalize_start_time(start_time)

    if total_distance_m <= DISTANCE_EPSILON_M:
        start_node = route_path.nodes[0]
        return [
            GeneratedTrackPoint(
                seconds_from_start=0.0,
                timestamp=normalized_start_time,
                lat=start_node.lat,
                lon=start_node.lon,
                speed_mps=0.0,
                course_deg=0.0,
                altitude_m=start_node.altitude_m,
            )
        ]

    duration_seconds = total_distance_m / target_speed_mps
    sample_times = _build_sample_times(
        duration_seconds=duration_seconds,
        sample_interval_seconds=1.0 / sample_rate_hz,
    )

    provisional_points: list[GeneratedTrackPoint] = []
    for seconds_from_start in sample_times:
        lat, lon, altitude_m = _position_at_distance(
            route_path.nodes,
            segment_lengths,
            min(total_distance_m, target_speed_mps * seconds_from_start),
        )
        timestamp = None
        if normalized_start_time is not None:
            timestamp = normalized_start_time + timedelta(seconds=seconds_from_start)
        provisional_points.append(
            GeneratedTrackPoint(
                seconds_from_start=seconds_from_start,
                timestamp=timestamp,
                lat=lat,
                lon=lon,
                speed_mps=target_speed_mps,
                course_deg=0.0,
                altitude_m=altitude_m,
            )
        )

    courses = _estimate_courses(provisional_points)
    return [
        GeneratedTrackPoint(
            seconds_from_start=point.seconds_from_start,
            timestamp=point.timestamp,
            lat=point.lat,
            lon=point.lon,
            speed_mps=point.speed_mps,
            course_deg=course_deg,
            altitude_m=point.altitude_m,
        )
        for point, course_deg in zip(provisional_points, courses)
    ]


def _segment_lengths(nodes: list[RouteNode]) -> list[float]:
    return [
        haversine_m(first.lat, first.lon, second.lat, second.lon)
        for first, second in zip(nodes, nodes[1:])
    ]


def _build_sample_times(
    *,
    duration_seconds: float,
    sample_interval_seconds: float,
) -> list[float]:
    sample_times = [0.0]
    current = sample_interval_seconds
    while current < duration_seconds - 1e-9:
        sample_times.append(current)
        current += sample_interval_seconds

    if duration_seconds > 0.0:
        sample_times.append(duration_seconds)

    return sample_times


def _position_at_distance(
    nodes: list[RouteNode],
    segment_lengths: list[float],
    distance_m: float,
) -> tuple[float, float, float]:
    if distance_m <= DISTANCE_EPSILON_M:
        start = nodes[0]
        return start.lat, start.lon, start.altitude_m

    travelled_m = 0.0
    last_segment_index = len(segment_lengths) - 1

    for index, (start, end, segment_length_m) in enumerate(
        zip(nodes, nodes[1:], segment_lengths)
    ):
        next_distance_m = travelled_m + segment_length_m
        if (
            index == last_segment_index
            or distance_m <= next_distance_m + DISTANCE_EPSILON_M
        ):
            if segment_length_m <= DISTANCE_EPSILON_M:
                return end.lat, end.lon, end.altitude_m

            segment_fraction = (distance_m - travelled_m) / segment_length_m
            segment_fraction = min(1.0, max(0.0, segment_fraction))
            return (
                start.lat + ((end.lat - start.lat) * segment_fraction),
                start.lon + ((end.lon - start.lon) * segment_fraction),
                start.altitude_m + ((end.altitude_m - start.altitude_m) * segment_fraction),
            )

        travelled_m = next_distance_m

    end = nodes[-1]
    return end.lat, end.lon, end.altitude_m


def _estimate_courses(points: list[GeneratedTrackPoint]) -> list[float]:
    if not points:
        return []
    if len(points) == 1:
        return [0.0]

    courses: list[float] = []
    last_course = 0.0
    for current, following in zip(points, points[1:]):
        course = bearing_deg(current.lat, current.lon, following.lat, following.lon)
        if (
            math.isclose(current.lat, following.lat, abs_tol=1e-12)
            and math.isclose(current.lon, following.lon, abs_tol=1e-12)
        ):
            course = last_course
        else:
            last_course = course
        courses.append(course)

    courses.append(last_course)
    return courses


def _normalize_start_time(start_time: datetime | None) -> datetime | None:
    if start_time is None:
        return None
    if start_time.tzinfo is None:
        return start_time.replace(tzinfo=timezone.utc)
    return start_time.astimezone(timezone.utc)
