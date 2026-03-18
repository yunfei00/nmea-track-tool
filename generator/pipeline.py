from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from generator.kinematics import interpolate_route_path, route_path_length_m
from generator.models import GeneratedTrackPoint, RoutePath
from generator.nmea_generator import generate_nmea_lines, write_nmea_file
from generator.router import MockRoutingProvider, RoutingProvider

DEFAULT_START_TIME = datetime(1970, 1, 1, tzinfo=timezone.utc)


@dataclass(slots=True)
class GenerationResult:
    route_path: RoutePath
    track_points: list[GeneratedTrackPoint]
    nmea_lines: list[str]

    @property
    def route_distance_m(self) -> float:
        return route_path_length_m(self.route_path)


def generate_track(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    *,
    routing_provider: RoutingProvider | None = None,
    sample_rate_hz: float = 1.0,
    target_speed_mps: float = 13.89,
    start_time: datetime | None = None,
    altitude_m: float = 0.0,
) -> GenerationResult:
    provider = routing_provider or MockRoutingProvider()
    normalized_start_time = _normalize_start_time(start_time) or DEFAULT_START_TIME

    route_path = provider.plan_route(
        start_lat,
        start_lon,
        end_lat,
        end_lon,
        altitude_m=altitude_m,
    )
    track_points = interpolate_route_path(
        route_path,
        sample_rate_hz=sample_rate_hz,
        target_speed_mps=target_speed_mps,
        start_time=normalized_start_time,
    )
    nmea_lines = generate_nmea_lines(track_points, start_time=normalized_start_time)
    return GenerationResult(
        route_path=route_path,
        track_points=track_points,
        nmea_lines=nmea_lines,
    )


def generate_track_to_nmea_file(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    output_path: str | Path,
    *,
    routing_provider: RoutingProvider | None = None,
    sample_rate_hz: float = 1.0,
    target_speed_mps: float = 13.89,
    start_time: datetime | None = None,
    altitude_m: float = 0.0,
) -> GenerationResult:
    result = generate_track(
        start_lat,
        start_lon,
        end_lat,
        end_lon,
        routing_provider=routing_provider,
        sample_rate_hz=sample_rate_hz,
        target_speed_mps=target_speed_mps,
        start_time=start_time,
        altitude_m=altitude_m,
    )
    write_nmea_file(result.track_points, output_path, start_time=start_time or DEFAULT_START_TIME)
    return result


def _normalize_start_time(start_time: datetime | None) -> datetime | None:
    if start_time is None:
        return None
    if start_time.tzinfo is None:
        return start_time.replace(tzinfo=timezone.utc)
    return start_time.astimezone(timezone.utc)
