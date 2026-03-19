from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Protocol

from core.geo import haversine_m
from generator.kinematics import bearing_deg
from generator.models import RoutePath, StopSegment

DEFAULT_TRAFFIC_LIGHT_STOP_PROBABILITY = 0.3
DEFAULT_TRAFFIC_LIGHT_MIN_STOP_DURATION_S = 2.0
DEFAULT_TRAFFIC_LIGHT_MAX_STOP_DURATION_S = 10.0
DEFAULT_TRAFFIC_LIGHT_ANGLE_THRESHOLD_DEG = 45.0
DEFAULT_MIN_CANDIDATE_SPACING_M = 60.0


class RandomSource(Protocol):
    def random(self) -> float:
        """Return the next pseudorandom value in [0.0, 1.0)."""

    def uniform(self, start: float, end: float) -> float:
        """Return a pseudorandom value in [start, end]."""


@dataclass(slots=True)
class TrafficLightConfig:
    stop_probability: float = DEFAULT_TRAFFIC_LIGHT_STOP_PROBABILITY
    min_stop_duration_s: float = DEFAULT_TRAFFIC_LIGHT_MIN_STOP_DURATION_S
    max_stop_duration_s: float = DEFAULT_TRAFFIC_LIGHT_MAX_STOP_DURATION_S
    angle_threshold_deg: float = DEFAULT_TRAFFIC_LIGHT_ANGLE_THRESHOLD_DEG
    min_candidate_spacing_m: float = DEFAULT_MIN_CANDIDATE_SPACING_M

    def __post_init__(self) -> None:
        if not 0.0 <= self.stop_probability <= 1.0:
            raise ValueError("stop_probability must be in [0, 1].")
        if self.min_stop_duration_s < 0.0:
            raise ValueError("min_stop_duration_s must be non-negative.")
        if self.max_stop_duration_s < self.min_stop_duration_s:
            raise ValueError(
                "max_stop_duration_s must be greater than or equal to min_stop_duration_s."
            )
        if not 0.0 <= self.angle_threshold_deg <= 180.0:
            raise ValueError("angle_threshold_deg must be in [0, 180].")
        if self.min_candidate_spacing_m < 0.0:
            raise ValueError("min_candidate_spacing_m must be non-negative.")


@dataclass(slots=True)
class TrafficLightCandidate:
    node_index: int
    path_distance_m: float
    lat: float
    lon: float
    turn_angle_deg: float


def detect_candidate_stop_points(
    route_path: RoutePath,
    *,
    angle_threshold_deg: float = DEFAULT_TRAFFIC_LIGHT_ANGLE_THRESHOLD_DEG,
    min_candidate_spacing_m: float = DEFAULT_MIN_CANDIDATE_SPACING_M,
) -> list[TrafficLightCandidate]:
    if angle_threshold_deg < 0.0 or angle_threshold_deg > 180.0:
        raise ValueError("angle_threshold_deg must be in [0, 180].")
    if min_candidate_spacing_m < 0.0:
        raise ValueError("min_candidate_spacing_m must be non-negative.")

    cumulative_distances = _cumulative_node_distances(route_path)
    candidates: list[TrafficLightCandidate] = []

    for node_index in range(1, len(route_path.nodes) - 1):
        previous_node = route_path.nodes[node_index - 1]
        current_node = route_path.nodes[node_index]
        next_node = route_path.nodes[node_index + 1]

        inbound_bearing = bearing_deg(
            previous_node.lat,
            previous_node.lon,
            current_node.lat,
            current_node.lon,
        )
        outbound_bearing = bearing_deg(
            current_node.lat,
            current_node.lon,
            next_node.lat,
            next_node.lon,
        )
        turn_angle_deg = _turn_angle_deg(inbound_bearing, outbound_bearing)
        if turn_angle_deg < angle_threshold_deg:
            continue

        candidate = TrafficLightCandidate(
            node_index=node_index,
            path_distance_m=cumulative_distances[node_index],
            lat=current_node.lat,
            lon=current_node.lon,
            turn_angle_deg=turn_angle_deg,
        )
        if (
            candidates
            and candidate.path_distance_m - candidates[-1].path_distance_m < min_candidate_spacing_m
        ):
            if candidate.turn_angle_deg > candidates[-1].turn_angle_deg:
                candidates[-1] = candidate
            continue

        candidates.append(candidate)

    return candidates


def simulate_traffic_light_stop_segments(
    route_path: RoutePath,
    *,
    config: TrafficLightConfig | None = None,
    rng: RandomSource | None = None,
) -> list[StopSegment]:
    resolved_config = config or TrafficLightConfig()
    random_source = rng or random.Random()
    candidates = detect_candidate_stop_points(
        route_path,
        angle_threshold_deg=resolved_config.angle_threshold_deg,
        min_candidate_spacing_m=resolved_config.min_candidate_spacing_m,
    )

    stop_segments: list[StopSegment] = []
    for candidate in candidates:
        if random_source.random() >= resolved_config.stop_probability:
            continue

        duration_s = random_source.uniform(
            resolved_config.min_stop_duration_s,
            resolved_config.max_stop_duration_s,
        )
        stop_segments.append(
            StopSegment(
                path_distance_m=candidate.path_distance_m,
                duration_s=duration_s,
            )
        )

    return stop_segments


def _cumulative_node_distances(route_path: RoutePath) -> list[float]:
    distances = [0.0]
    total_distance_m = 0.0
    for first, second in zip(route_path.nodes, route_path.nodes[1:]):
        total_distance_m += haversine_m(first.lat, first.lon, second.lat, second.lon)
        distances.append(total_distance_m)
    return distances


def _turn_angle_deg(inbound_bearing: float, outbound_bearing: float) -> float:
    raw_difference = abs(outbound_bearing - inbound_bearing) % 360.0
    return min(raw_difference, 360.0 - raw_difference)
