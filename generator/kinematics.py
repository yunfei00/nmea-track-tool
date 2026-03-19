from __future__ import annotations

from dataclasses import dataclass
import math
from datetime import datetime, timedelta, timezone

from core.geo import haversine_m
from generator.models import GeneratedTrackPoint, RouteNode, RoutePath, StopSegment

DISTANCE_EPSILON_M = 1e-6
TIME_EPSILON_S = 1e-9
SPEED_EPSILON_MPS = 1e-6
DEFAULT_ACCELERATION_MPS2 = 2.0
DEFAULT_DECELERATION_MPS2 = 2.5


@dataclass(slots=True)
class _MotionLeg:
    start_distance_m: float
    end_distance_m: float
    peak_speed_mps: float
    acceleration_mps2: float
    deceleration_mps2: float
    acceleration_duration_s: float
    cruise_duration_s: float
    deceleration_duration_s: float
    acceleration_distance_m: float
    cruise_distance_m: float

    @property
    def distance_m(self) -> float:
        return self.end_distance_m - self.start_distance_m

    @property
    def duration_s(self) -> float:
        return (
            self.acceleration_duration_s
            + self.cruise_duration_s
            + self.deceleration_duration_s
        )


@dataclass(slots=True)
class _MotionSample:
    seconds_from_start: float
    distance_m: float
    speed_mps: float


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
    acceleration_mps2: float = DEFAULT_ACCELERATION_MPS2,
    deceleration_mps2: float = DEFAULT_DECELERATION_MPS2,
    stop_segments: list[StopSegment] | None = None,
    start_time: datetime | None = None,
) -> list[GeneratedTrackPoint]:
    if sample_rate_hz <= 0.0:
        raise ValueError("sample_rate_hz must be greater than zero.")
    if target_speed_mps <= 0.0:
        raise ValueError("target_speed_mps must be greater than zero.")
    if acceleration_mps2 <= 0.0:
        raise ValueError("acceleration_mps2 must be greater than zero.")
    if deceleration_mps2 <= 0.0:
        raise ValueError("deceleration_mps2 must be greater than zero.")

    segment_lengths = _segment_lengths(route_path.nodes)
    total_distance_m = sum(segment_lengths)
    normalized_start_time = _normalize_start_time(start_time)
    normalized_stop_segments = _normalize_stop_segments(
        stop_segments or [],
        total_distance_m=total_distance_m,
    )

    if total_distance_m <= DISTANCE_EPSILON_M:
        start_node = route_path.nodes[0]
        stationary_samples = [
            _MotionSample(
                seconds_from_start=0.0,
                distance_m=0.0,
                speed_mps=0.0,
            )
        ]
        if normalized_stop_segments:
            stationary_samples.extend(
                _build_hold_samples(
                    start_time_s=0.0,
                    distance_m=0.0,
                    hold_duration_s=sum(stop.duration_s for stop in normalized_stop_segments),
                    sample_interval_s=1.0 / sample_rate_hz,
                )
            )
        return [
            GeneratedTrackPoint(
                seconds_from_start=sample.seconds_from_start,
                timestamp=_timestamp_at_seconds(normalized_start_time, sample.seconds_from_start),
                lat=start_node.lat,
                lon=start_node.lon,
                speed_mps=sample.speed_mps,
                course_deg=0.0,
                altitude_m=start_node.altitude_m,
            )
            for sample in stationary_samples
        ]

    motion_samples = _build_motion_samples(
        total_distance_m=total_distance_m,
        sample_interval_s=1.0 / sample_rate_hz,
        target_speed_mps=target_speed_mps,
        acceleration_mps2=acceleration_mps2,
        deceleration_mps2=deceleration_mps2,
        stop_segments=normalized_stop_segments,
    )

    provisional_points: list[GeneratedTrackPoint] = []
    for sample in motion_samples:
        lat, lon, altitude_m = _position_at_distance(
            route_path.nodes,
            segment_lengths,
            sample.distance_m,
        )
        provisional_points.append(
            GeneratedTrackPoint(
                seconds_from_start=sample.seconds_from_start,
                timestamp=_timestamp_at_seconds(
                    normalized_start_time,
                    sample.seconds_from_start,
                ),
                lat=lat,
                lon=lon,
                speed_mps=sample.speed_mps,
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


def _build_motion_samples(
    *,
    total_distance_m: float,
    sample_interval_s: float,
    target_speed_mps: float,
    acceleration_mps2: float,
    deceleration_mps2: float,
    stop_segments: list[StopSegment],
) -> list[_MotionSample]:
    samples = [_MotionSample(seconds_from_start=0.0, distance_m=0.0, speed_mps=0.0)]
    current_time_s = 0.0

    initial_hold_duration_s = sum(
        stop.duration_s
        for stop in stop_segments
        if stop.path_distance_m <= DISTANCE_EPSILON_M
    )
    if initial_hold_duration_s > TIME_EPSILON_S:
        hold_samples = _build_hold_samples(
            start_time_s=current_time_s,
            distance_m=0.0,
            hold_duration_s=initial_hold_duration_s,
            sample_interval_s=sample_interval_s,
        )
        samples.extend(hold_samples)
        current_time_s += initial_hold_duration_s

    mid_route_stops = [
        stop
        for stop in stop_segments
        if DISTANCE_EPSILON_M < stop.path_distance_m < total_distance_m - DISTANCE_EPSILON_M
    ]
    final_hold_duration_s = sum(
        stop.duration_s
        for stop in stop_segments
        if stop.path_distance_m >= total_distance_m - DISTANCE_EPSILON_M
    )

    boundary_distances = [0.0, *[stop.path_distance_m for stop in mid_route_stops], total_distance_m]
    hold_after_distance = {
        stop.path_distance_m: stop.duration_s
        for stop in mid_route_stops
    }
    if final_hold_duration_s > TIME_EPSILON_S:
        hold_after_distance[total_distance_m] = final_hold_duration_s

    for start_distance_m, end_distance_m in zip(boundary_distances, boundary_distances[1:]):
        leg = _build_motion_leg(
            start_distance_m=start_distance_m,
            end_distance_m=end_distance_m,
            target_speed_mps=target_speed_mps,
            acceleration_mps2=acceleration_mps2,
            deceleration_mps2=deceleration_mps2,
        )
        leg_sample_times = _build_follow_up_sample_times(
            duration_s=leg.duration_s,
            sample_interval_s=sample_interval_s,
        )
        for relative_time_s in leg_sample_times:
            distance_into_leg_m, speed_mps = _distance_and_speed_at_leg_time(
                leg,
                relative_time_s,
            )
            samples.append(
                _MotionSample(
                    seconds_from_start=current_time_s + relative_time_s,
                    distance_m=leg.start_distance_m + distance_into_leg_m,
                    speed_mps=speed_mps,
                )
            )
        current_time_s += leg.duration_s

        hold_duration_s = hold_after_distance.get(end_distance_m, 0.0)
        if hold_duration_s > TIME_EPSILON_S:
            hold_samples = _build_hold_samples(
                start_time_s=current_time_s,
                distance_m=end_distance_m,
                hold_duration_s=hold_duration_s,
                sample_interval_s=sample_interval_s,
            )
            samples.extend(hold_samples)
            current_time_s += hold_duration_s

    return samples


def _build_motion_leg(
    *,
    start_distance_m: float,
    end_distance_m: float,
    target_speed_mps: float,
    acceleration_mps2: float,
    deceleration_mps2: float,
) -> _MotionLeg:
    distance_m = end_distance_m - start_distance_m
    if distance_m <= DISTANCE_EPSILON_M:
        return _MotionLeg(
            start_distance_m=start_distance_m,
            end_distance_m=end_distance_m,
            peak_speed_mps=0.0,
            acceleration_mps2=acceleration_mps2,
            deceleration_mps2=deceleration_mps2,
            acceleration_duration_s=0.0,
            cruise_duration_s=0.0,
            deceleration_duration_s=0.0,
            acceleration_distance_m=0.0,
            cruise_distance_m=0.0,
        )

    full_acceleration_distance_m = (target_speed_mps**2) / (2.0 * acceleration_mps2)
    full_deceleration_distance_m = (target_speed_mps**2) / (2.0 * deceleration_mps2)

    if distance_m >= full_acceleration_distance_m + full_deceleration_distance_m:
        peak_speed_mps = target_speed_mps
        acceleration_distance_m = full_acceleration_distance_m
        deceleration_distance_m = full_deceleration_distance_m
        cruise_distance_m = distance_m - acceleration_distance_m - deceleration_distance_m
    else:
        peak_speed_mps = math.sqrt(
            (2.0 * distance_m)
            / ((1.0 / acceleration_mps2) + (1.0 / deceleration_mps2))
        )
        acceleration_distance_m = (peak_speed_mps**2) / (2.0 * acceleration_mps2)
        deceleration_distance_m = (peak_speed_mps**2) / (2.0 * deceleration_mps2)
        cruise_distance_m = max(0.0, distance_m - acceleration_distance_m - deceleration_distance_m)

    acceleration_duration_s = peak_speed_mps / acceleration_mps2 if peak_speed_mps > 0.0 else 0.0
    deceleration_duration_s = peak_speed_mps / deceleration_mps2 if peak_speed_mps > 0.0 else 0.0
    cruise_duration_s = cruise_distance_m / peak_speed_mps if peak_speed_mps > 0.0 else 0.0

    return _MotionLeg(
        start_distance_m=start_distance_m,
        end_distance_m=end_distance_m,
        peak_speed_mps=peak_speed_mps,
        acceleration_mps2=acceleration_mps2,
        deceleration_mps2=deceleration_mps2,
        acceleration_duration_s=acceleration_duration_s,
        cruise_duration_s=cruise_duration_s,
        deceleration_duration_s=deceleration_duration_s,
        acceleration_distance_m=acceleration_distance_m,
        cruise_distance_m=cruise_distance_m,
    )


def _distance_and_speed_at_leg_time(
    leg: _MotionLeg,
    time_s: float,
) -> tuple[float, float]:
    if leg.duration_s <= TIME_EPSILON_S:
        return 0.0, 0.0

    if time_s >= leg.duration_s - TIME_EPSILON_S:
        return leg.distance_m, 0.0

    if time_s <= leg.acceleration_duration_s + TIME_EPSILON_S:
        clamped_time_s = min(time_s, leg.acceleration_duration_s)
        return (
            0.5 * leg.acceleration_mps2 * (clamped_time_s**2),
            leg.acceleration_mps2 * clamped_time_s,
        )

    if time_s <= leg.acceleration_duration_s + leg.cruise_duration_s + TIME_EPSILON_S:
        cruise_time_s = time_s - leg.acceleration_duration_s
        return (
            leg.acceleration_distance_m + (leg.peak_speed_mps * cruise_time_s),
            leg.peak_speed_mps,
        )

    deceleration_time_s = time_s - leg.acceleration_duration_s - leg.cruise_duration_s
    deceleration_distance_m = (
        (leg.peak_speed_mps * deceleration_time_s)
        - (0.5 * leg.deceleration_mps2 * (deceleration_time_s**2))
    )
    speed_mps = max(0.0, leg.peak_speed_mps - (leg.deceleration_mps2 * deceleration_time_s))
    return (
        leg.acceleration_distance_m + leg.cruise_distance_m + deceleration_distance_m,
        speed_mps,
    )


def _build_follow_up_sample_times(
    *,
    duration_s: float,
    sample_interval_s: float,
) -> list[float]:
    if duration_s <= TIME_EPSILON_S:
        return []

    sample_times: list[float] = []
    current = sample_interval_s
    while current < duration_s - TIME_EPSILON_S:
        sample_times.append(current)
        current += sample_interval_s

    sample_times.append(duration_s)
    return sample_times


def _build_hold_samples(
    *,
    start_time_s: float,
    distance_m: float,
    hold_duration_s: float,
    sample_interval_s: float,
) -> list[_MotionSample]:
    return [
        _MotionSample(
            seconds_from_start=start_time_s + relative_time_s,
            distance_m=distance_m,
            speed_mps=0.0,
        )
        for relative_time_s in _build_follow_up_sample_times(
            duration_s=hold_duration_s,
            sample_interval_s=sample_interval_s,
        )
    ]


def _normalize_stop_segments(
    stop_segments: list[StopSegment],
    *,
    total_distance_m: float,
) -> list[StopSegment]:
    normalized: list[StopSegment] = []
    for stop in sorted(stop_segments, key=lambda value: value.path_distance_m):
        if stop.duration_s <= TIME_EPSILON_S:
            continue

        if stop.path_distance_m > total_distance_m + DISTANCE_EPSILON_M:
            raise ValueError(
                "StopSegment path_distance_m cannot exceed the route length."
            )

        clamped_distance_m = min(max(0.0, stop.path_distance_m), total_distance_m)
        if normalized and math.isclose(
            normalized[-1].path_distance_m,
            clamped_distance_m,
            abs_tol=DISTANCE_EPSILON_M,
        ):
            normalized[-1] = StopSegment(
                path_distance_m=normalized[-1].path_distance_m,
                duration_s=normalized[-1].duration_s + stop.duration_s,
            )
            continue

        normalized.append(
            StopSegment(
                path_distance_m=clamped_distance_m,
                duration_s=stop.duration_s,
            )
        )

    return normalized


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
    last_index = len(points) - 1

    for index, point in enumerate(points):
        previous_is_same = index > 0 and _same_position(points[index - 1], point)
        next_is_same = index < last_index and _same_position(point, points[index + 1])

        if (
            point.speed_mps <= SPEED_EPSILON_MPS
            and last_course > 0.0
            and (previous_is_same or next_is_same or index == last_index)
        ):
            courses.append(last_course)
            continue

        next_distinct_index = _find_distinct_point_index(points, index, direction=1)
        if next_distinct_index is not None:
            course = bearing_deg(
                point.lat,
                point.lon,
                points[next_distinct_index].lat,
                points[next_distinct_index].lon,
            )
        else:
            previous_distinct_index = _find_distinct_point_index(points, index, direction=-1)
            if previous_distinct_index is None:
                course = last_course
            else:
                course = bearing_deg(
                    points[previous_distinct_index].lat,
                    points[previous_distinct_index].lon,
                    point.lat,
                    point.lon,
                )

        last_course = course
        courses.append(course)

    return courses


def _find_distinct_point_index(
    points: list[GeneratedTrackPoint],
    start_index: int,
    *,
    direction: int,
) -> int | None:
    index = start_index + direction
    while 0 <= index < len(points):
        if not _same_position(points[start_index], points[index]):
            return index
        index += direction
    return None


def _same_position(first: GeneratedTrackPoint, second: GeneratedTrackPoint) -> bool:
    return math.isclose(first.lat, second.lat, abs_tol=1e-12) and math.isclose(
        first.lon,
        second.lon,
        abs_tol=1e-12,
    )


def _normalize_start_time(start_time: datetime | None) -> datetime | None:
    if start_time is None:
        return None
    if start_time.tzinfo is None:
        return start_time.replace(tzinfo=timezone.utc)
    return start_time.astimezone(timezone.utc)


def _timestamp_at_seconds(
    start_time: datetime | None,
    seconds_from_start: float,
) -> datetime | None:
    if start_time is None:
        return None
    return start_time + timedelta(seconds=seconds_from_start)
