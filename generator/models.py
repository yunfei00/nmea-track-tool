from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

MPS_TO_KMH = 3.6
MPS_TO_KNOTS = 1.9438444924406


@dataclass(slots=True)
class RouteNode:
    lat: float
    lon: float
    altitude_m: float = 0.0
    node_id: str = ""

    def __post_init__(self) -> None:
        if not -90.0 <= self.lat <= 90.0:
            raise ValueError(f"RouteNode lat must be in [-90, 90], got {self.lat}.")
        if not -180.0 <= self.lon <= 180.0:
            raise ValueError(f"RouteNode lon must be in [-180, 180], got {self.lon}.")


@dataclass(slots=True)
class RoutePath:
    nodes: list[RouteNode]
    provider_name: str = ""

    def __post_init__(self) -> None:
        if len(self.nodes) < 2:
            raise ValueError("RoutePath must contain at least two RouteNode items.")


@dataclass(slots=True)
class StopSegment:
    path_distance_m: float
    duration_s: float

    def __post_init__(self) -> None:
        if self.path_distance_m < 0.0:
            raise ValueError("path_distance_m must be non-negative.")
        if self.duration_s < 0.0:
            raise ValueError("duration_s must be non-negative.")


@dataclass(slots=True)
class GeneratedTrackPoint:
    seconds_from_start: float
    lat: float
    lon: float
    speed_mps: float
    course_deg: float
    altitude_m: float = 0.0
    timestamp: datetime | None = None

    def __post_init__(self) -> None:
        if self.seconds_from_start < 0.0:
            raise ValueError("seconds_from_start must be non-negative.")
        if self.speed_mps < 0.0:
            raise ValueError("speed_mps must be non-negative.")
        if not -90.0 <= self.lat <= 90.0:
            raise ValueError(f"GeneratedTrackPoint lat must be in [-90, 90], got {self.lat}.")
        if not -180.0 <= self.lon <= 180.0:
            raise ValueError(f"GeneratedTrackPoint lon must be in [-180, 180], got {self.lon}.")
        self.course_deg = self.course_deg % 360.0

    @property
    def speed_kmh(self) -> float:
        return self.speed_mps * MPS_TO_KMH

    @property
    def speed_knots(self) -> float:
        return self.speed_mps * MPS_TO_KNOTS
