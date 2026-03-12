from __future__ import annotations

import math

EARTH_RADIUS_M = 6_371_000.0
KNOTS_TO_KMH = 1.852


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    latitude1 = math.radians(lat1)
    longitude1 = math.radians(lon1)
    latitude2 = math.radians(lat2)
    longitude2 = math.radians(lon2)

    delta_lat = latitude2 - latitude1
    delta_lon = longitude2 - longitude1

    haversine = (
        math.sin(delta_lat / 2.0) ** 2
        + math.cos(latitude1)
        * math.cos(latitude2)
        * math.sin(delta_lon / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(haversine)))


def knots_to_kmh(knots: float) -> float:
    return knots * KNOTS_TO_KMH


def calc_speed_kmh(distance_m: float, delta_seconds: float) -> float:
    if delta_seconds <= 0.0:
        raise ValueError("delta_seconds must be greater than zero.")
    return (distance_m / delta_seconds) * 3.6
