from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from generator.kinematics import (
    DEFAULT_ACCELERATION_MPS2,
    DEFAULT_DECELERATION_MPS2,
    interpolate_route_path,
    route_path_length_m,
)
from generator.models import GeneratedTrackPoint, RoutePath, StopSegment
from generator.nmea_generator import generate_nmea_lines, write_nmea_file
from generator.router import (
    DEFAULT_OSRM_BASE_URL,
    DEFAULT_OSRM_GEOMETRY_FORMAT,
    DEFAULT_OSRM_PROFILE,
    MockRoutingProvider,
    OSRMRoutingProvider,
    RoutingProvider,
)
from generator.traffic_lights import RandomSource, TrafficLightConfig, simulate_traffic_light_stop_segments

DEFAULT_START_TIME = datetime(1970, 1, 1, tzinfo=timezone.utc)


@dataclass(slots=True)
class GenerationResult:
    route_path: RoutePath
    track_points: list[GeneratedTrackPoint]
    nmea_lines: list[str]
    traffic_light_stop_segments: list[StopSegment] = field(default_factory=list)
    effective_stop_segments: list[StopSegment] = field(default_factory=list)

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
    routing_mode: str = "mock",
    osrm_base_url: str = DEFAULT_OSRM_BASE_URL,
    osrm_profile: str = DEFAULT_OSRM_PROFILE,
    osrm_geometry_format: str = DEFAULT_OSRM_GEOMETRY_FORMAT,
    osrm_request_timeout_s: float = 10.0,
    osrm_requester: Callable[[str, float], str] | None = None,
    sample_rate_hz: float = 1.0,
    target_speed_mps: float = 13.89,
    acceleration_mps2: float = DEFAULT_ACCELERATION_MPS2,
    deceleration_mps2: float = DEFAULT_DECELERATION_MPS2,
    stop_segments: list[StopSegment] | None = None,
    enable_traffic_lights: bool = False,
    traffic_light_config: TrafficLightConfig | None = None,
    traffic_light_rng: RandomSource | None = None,
    start_time: datetime | None = None,
    altitude_m: float = 0.0,
) -> GenerationResult:
    provider = routing_provider or _build_routing_provider(
        routing_mode=routing_mode,
        osrm_base_url=osrm_base_url,
        osrm_profile=osrm_profile,
        osrm_geometry_format=osrm_geometry_format,
        osrm_request_timeout_s=osrm_request_timeout_s,
        osrm_requester=osrm_requester,
    )
    normalized_start_time = _normalize_start_time(start_time) or DEFAULT_START_TIME

    route_path = provider.plan_route(
        start_lat,
        start_lon,
        end_lat,
        end_lon,
        altitude_m=altitude_m,
    )
    preview_track_points = interpolate_route_path(
        route_path,
        sample_rate_hz=sample_rate_hz,
        target_speed_mps=target_speed_mps,
        acceleration_mps2=acceleration_mps2,
        deceleration_mps2=deceleration_mps2,
        stop_segments=stop_segments,
        start_time=normalized_start_time,
    )
    traffic_light_stop_segments: list[StopSegment] = []
    effective_stop_segments = list(stop_segments or [])
    track_points = preview_track_points

    if enable_traffic_lights:
        traffic_light_stop_segments = simulate_traffic_light_stop_segments(
            route_path,
            config=traffic_light_config,
            rng=traffic_light_rng,
        )
        if traffic_light_stop_segments:
            effective_stop_segments.extend(traffic_light_stop_segments)
            track_points = interpolate_route_path(
                route_path,
                sample_rate_hz=sample_rate_hz,
                target_speed_mps=target_speed_mps,
                acceleration_mps2=acceleration_mps2,
                deceleration_mps2=deceleration_mps2,
                stop_segments=effective_stop_segments,
                start_time=normalized_start_time,
            )

    nmea_lines = generate_nmea_lines(track_points, start_time=normalized_start_time)
    return GenerationResult(
        route_path=route_path,
        track_points=track_points,
        nmea_lines=nmea_lines,
        traffic_light_stop_segments=traffic_light_stop_segments,
        effective_stop_segments=effective_stop_segments,
    )


def generate_track_to_nmea_file(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    output_path: str | Path,
    *,
    routing_provider: RoutingProvider | None = None,
    routing_mode: str = "mock",
    osrm_base_url: str = DEFAULT_OSRM_BASE_URL,
    osrm_profile: str = DEFAULT_OSRM_PROFILE,
    osrm_geometry_format: str = DEFAULT_OSRM_GEOMETRY_FORMAT,
    osrm_request_timeout_s: float = 10.0,
    osrm_requester: Callable[[str, float], str] | None = None,
    sample_rate_hz: float = 1.0,
    target_speed_mps: float = 13.89,
    acceleration_mps2: float = DEFAULT_ACCELERATION_MPS2,
    deceleration_mps2: float = DEFAULT_DECELERATION_MPS2,
    stop_segments: list[StopSegment] | None = None,
    enable_traffic_lights: bool = False,
    traffic_light_config: TrafficLightConfig | None = None,
    traffic_light_rng: RandomSource | None = None,
    start_time: datetime | None = None,
    altitude_m: float = 0.0,
) -> GenerationResult:
    result = generate_track(
        start_lat,
        start_lon,
        end_lat,
        end_lon,
        routing_provider=routing_provider,
        routing_mode=routing_mode,
        osrm_base_url=osrm_base_url,
        osrm_profile=osrm_profile,
        osrm_geometry_format=osrm_geometry_format,
        osrm_request_timeout_s=osrm_request_timeout_s,
        osrm_requester=osrm_requester,
        sample_rate_hz=sample_rate_hz,
        target_speed_mps=target_speed_mps,
        acceleration_mps2=acceleration_mps2,
        deceleration_mps2=deceleration_mps2,
        stop_segments=stop_segments,
        enable_traffic_lights=enable_traffic_lights,
        traffic_light_config=traffic_light_config,
        traffic_light_rng=traffic_light_rng,
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


def _build_routing_provider(
    *,
    routing_mode: str,
    osrm_base_url: str,
    osrm_profile: str,
    osrm_geometry_format: str,
    osrm_request_timeout_s: float,
    osrm_requester: Callable[[str, float], str] | None,
) -> RoutingProvider:
    if routing_mode == "mock":
        return MockRoutingProvider()
    if routing_mode == "osrm":
        return OSRMRoutingProvider(
            base_url=osrm_base_url,
            profile=osrm_profile,
            geometry_format=osrm_geometry_format,
            request_timeout_s=osrm_request_timeout_s,
            requester=osrm_requester,
        )
    raise ValueError("routing_mode must be either 'mock' or 'osrm'.")
