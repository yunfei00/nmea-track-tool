from __future__ import annotations

from abc import ABC, abstractmethod
import json
from typing import Any, Callable
from urllib import error, parse, request

from generator.models import RouteNode, RoutePath

COORDINATE_EPSILON = 1e-12
DEFAULT_OSRM_BASE_URL = "https://router.project-osrm.org"
DEFAULT_OSRM_PROFILE = "driving"
DEFAULT_OSRM_GEOMETRY_FORMAT = "geojson"
SUPPORTED_OSRM_GEOMETRIES = {"geojson", "polyline", "polyline6"}


class RoutingError(RuntimeError):
    """Raised when route planning cannot return a usable path."""


class RoutingProvider(ABC):
    @abstractmethod
    def plan_route(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        *,
        altitude_m: float = 0.0,
    ) -> RoutePath:
        """Build a route path between start and end coordinates."""


class OSRMRoutingProvider(RoutingProvider):
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_OSRM_BASE_URL,
        profile: str = DEFAULT_OSRM_PROFILE,
        geometry_format: str = DEFAULT_OSRM_GEOMETRY_FORMAT,
        request_timeout_s: float = 10.0,
        provider_name: str = "osrm",
        requester: Callable[[str, float], str] | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError("base_url must not be empty.")
        if not profile.strip():
            raise ValueError("profile must not be empty.")
        if geometry_format not in SUPPORTED_OSRM_GEOMETRIES:
            raise ValueError(
                "geometry_format must be one of "
                f"{sorted(SUPPORTED_OSRM_GEOMETRIES)}, got {geometry_format!r}."
            )
        if request_timeout_s <= 0.0:
            raise ValueError("request_timeout_s must be greater than zero.")

        self.base_url = base_url.rstrip("/")
        self.profile = profile
        self.geometry_format = geometry_format
        self.request_timeout_s = request_timeout_s
        self.provider_name = provider_name
        self.requester = requester or _default_requester

    def plan_route(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        *,
        altitude_m: float = 0.0,
    ) -> RoutePath:
        url = self._build_route_url(start_lat, start_lon, end_lat, end_lon)

        try:
            response_text = self.requester(url, self.request_timeout_s)
        except error.HTTPError as exc:
            raise RoutingError(f"OSRM request failed with HTTP {exc.code}.") from exc
        except error.URLError as exc:
            raise RoutingError(f"OSRM request failed: {exc.reason}.") from exc
        except OSError as exc:
            raise RoutingError(f"OSRM request failed: {exc}.") from exc

        try:
            payload = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise RoutingError("OSRM response was not valid JSON.") from exc

        return route_path_from_osrm_response(
            payload,
            provider_name=self.provider_name,
            altitude_m=altitude_m,
            geometry_format=self.geometry_format,
        )

    def _build_route_url(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
    ) -> str:
        coordinates = f"{start_lon:.6f},{start_lat:.6f};{end_lon:.6f},{end_lat:.6f}"
        query = parse.urlencode(
            {
                "overview": "full",
                "steps": "false",
                "geometries": self.geometry_format,
            }
        )
        return f"{self.base_url}/route/v1/{self.profile}/{coordinates}?{query}"


class MockRoutingProvider(RoutingProvider):
    def __init__(self, *, provider_name: str = "mock", bend_ratio: float = 0.5) -> None:
        if not 0.0 < bend_ratio < 1.0:
            raise ValueError("bend_ratio must be between 0 and 1.")
        self.provider_name = provider_name
        self.bend_ratio = bend_ratio

    def plan_route(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        *,
        altitude_m: float = 0.0,
    ) -> RoutePath:
        start = RouteNode(start_lat, start_lon, altitude_m=altitude_m, node_id="start")
        end = RouteNode(end_lat, end_lon, altitude_m=altitude_m, node_id="end")

        delta_lat = end_lat - start_lat
        delta_lon = end_lon - start_lon

        if (
            abs(delta_lat) <= COORDINATE_EPSILON
            or abs(delta_lon) <= COORDINATE_EPSILON
        ):
            nodes = [start, end]
        elif abs(delta_lat) >= abs(delta_lon):
            bend_lat = start_lat + (delta_lat * self.bend_ratio)
            nodes = [
                start,
                RouteNode(bend_lat, start_lon, altitude_m=altitude_m, node_id="turn_1"),
                RouteNode(bend_lat, end_lon, altitude_m=altitude_m, node_id="turn_2"),
                end,
            ]
        else:
            bend_lon = start_lon + (delta_lon * self.bend_ratio)
            nodes = [
                start,
                RouteNode(start_lat, bend_lon, altitude_m=altitude_m, node_id="turn_1"),
                RouteNode(end_lat, bend_lon, altitude_m=altitude_m, node_id="turn_2"),
                end,
            ]

        return RoutePath(nodes=_dedupe_adjacent_nodes(nodes), provider_name=self.provider_name)


def route_path_from_osrm_response(
    payload: dict[str, Any],
    *,
    provider_name: str = "osrm",
    altitude_m: float = 0.0,
    geometry_format: str = DEFAULT_OSRM_GEOMETRY_FORMAT,
) -> RoutePath:
    if payload.get("code") != "Ok":
        message = payload.get("message") or payload.get("code") or "unknown OSRM error"
        raise RoutingError(f"OSRM routing failed: {message}.")

    routes = payload.get("routes")
    if not isinstance(routes, list) or not routes:
        raise RoutingError("OSRM returned no routes.")

    route = routes[0]
    geometry = route.get("geometry")
    if geometry in (None, ""):
        raise RoutingError("OSRM route geometry is missing.")

    nodes = _route_nodes_from_osrm_geometry(
        geometry,
        altitude_m=altitude_m,
        geometry_format=geometry_format,
    )
    deduped_nodes = _dedupe_adjacent_nodes(nodes)
    if len(deduped_nodes) < 2:
        raise RoutingError("OSRM route geometry does not contain enough coordinates.")

    return RoutePath(nodes=deduped_nodes, provider_name=provider_name)


def _route_nodes_from_osrm_geometry(
    geometry: Any,
    *,
    altitude_m: float,
    geometry_format: str,
) -> list[RouteNode]:
    coordinates: list[tuple[float, float]]
    if isinstance(geometry, dict):
        coordinates = _coordinates_from_geojson_geometry(geometry)
    elif isinstance(geometry, str):
        precision = 6 if geometry_format == "polyline6" else 5
        coordinates = _coordinates_from_polyline(geometry, precision=precision)
    else:
        raise RoutingError("OSRM route geometry has an unsupported format.")

    if len(coordinates) < 2:
        raise RoutingError("OSRM route geometry is empty.")

    return [
        RouteNode(
            lat=lat,
            lon=lon,
            altitude_m=altitude_m,
            node_id=f"route_{index}",
        )
        for index, (lat, lon) in enumerate(coordinates)
    ]


def _coordinates_from_geojson_geometry(geometry: dict[str, Any]) -> list[tuple[float, float]]:
    if geometry.get("type") != "LineString":
        raise RoutingError("OSRM GeoJSON geometry must be a LineString.")

    raw_coordinates = geometry.get("coordinates")
    if not isinstance(raw_coordinates, list):
        raise RoutingError("OSRM GeoJSON geometry is missing coordinates.")

    coordinates: list[tuple[float, float]] = []
    for raw_coordinate in raw_coordinates:
        if not isinstance(raw_coordinate, list) or len(raw_coordinate) < 2:
            raise RoutingError("OSRM GeoJSON coordinate is invalid.")
        lon = float(raw_coordinate[0])
        lat = float(raw_coordinate[1])
        coordinates.append((lat, lon))
    return coordinates


def _coordinates_from_polyline(polyline_text: str, *, precision: int) -> list[tuple[float, float]]:
    scale = 10**precision
    latitude = 0
    longitude = 0
    index = 0
    coordinates: list[tuple[float, float]] = []

    while index < len(polyline_text):
        latitude_delta, index = _decode_polyline_value(polyline_text, index)
        longitude_delta, index = _decode_polyline_value(polyline_text, index)
        latitude += latitude_delta
        longitude += longitude_delta
        coordinates.append((latitude / scale, longitude / scale))

    return coordinates


def _decode_polyline_value(polyline_text: str, start_index: int) -> tuple[int, int]:
    result = 0
    shift = 0
    index = start_index

    while True:
        if index >= len(polyline_text):
            raise RoutingError("OSRM polyline geometry is truncated.")

        chunk = ord(polyline_text[index]) - 63
        index += 1
        result |= (chunk & 0x1F) << shift
        shift += 5
        if chunk < 0x20:
            break

    delta = ~(result >> 1) if result & 1 else (result >> 1)
    return delta, index


def _dedupe_adjacent_nodes(nodes: list[RouteNode]) -> list[RouteNode]:
    if not nodes:
        return []

    deduped = [nodes[0]]
    for node in nodes[1:]:
        previous = deduped[-1]
        if (
            abs(node.lat - previous.lat) <= COORDINATE_EPSILON
            and abs(node.lon - previous.lon) <= COORDINATE_EPSILON
            and abs(node.altitude_m - previous.altitude_m) <= COORDINATE_EPSILON
        ):
            continue
        deduped.append(node)

    if len(deduped) == 1:
        only = deduped[0]
        deduped.append(
            RouteNode(
                only.lat,
                only.lon,
                altitude_m=only.altitude_m,
                node_id="end",
            )
        )

    return deduped


def _default_requester(url: str, timeout_s: float) -> str:
    with request.urlopen(url, timeout=timeout_s) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset)
