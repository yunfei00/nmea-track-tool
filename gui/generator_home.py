from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

DEFAULT_MAP_CITY_NAME = "Beijing"


@dataclass(frozen=True)
class MapViewport:
    latitude: float
    longitude: float
    zoom: int = 11

    def to_payload(self) -> dict[str, float | int]:
        return {
            "lat": self.latitude,
            "lon": self.longitude,
            "zoom": int(self.zoom),
        }


DEFAULT_MAP_VIEW = MapViewport(latitude=39.9042, longitude=116.4074, zoom=11)


class GeocoderLike(Protocol):
    def geocode(self, query: str) -> tuple[float, float]:
        ...


@dataclass(frozen=True)
class ResolvedLocationInput:
    latitude: float
    longitude: float
    source: Literal["coordinates", "address"]
    query: str

    @property
    def coordinates(self) -> tuple[float, float]:
        return self.latitude, self.longitude


def default_map_state_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "nmea-track-tool" / "map_home.json"
    return Path.home() / ".nmea-track-tool" / "map_home.json"


def choose_startup_map_view(
    saved_view: MapViewport | None,
    *,
    default_view: MapViewport = DEFAULT_MAP_VIEW,
) -> MapViewport:
    return saved_view or default_view


def load_saved_map_view(path: Path | None = None) -> MapViewport | None:
    state_path = path or default_map_state_path()
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    try:
        latitude = _parse_viewport_field(payload, "lat", -90.0, 90.0)
        longitude = _parse_viewport_field(payload, "lon", -180.0, 180.0)
        zoom = int(_parse_viewport_field(payload, "zoom", 1.0, 19.0))
    except (TypeError, ValueError):
        return None

    return MapViewport(latitude=latitude, longitude=longitude, zoom=zoom)


def load_startup_map_view(
    *,
    path: Path | None = None,
    default_view: MapViewport = DEFAULT_MAP_VIEW,
) -> MapViewport:
    saved_view = load_saved_map_view(path)
    return choose_startup_map_view(saved_view, default_view=default_view)


def save_map_view(
    view: MapViewport,
    *,
    path: Path | None = None,
) -> Path:
    state_path = path or default_map_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(view.to_payload(), separators=(",", ":")),
        encoding="utf-8",
    )
    return state_path


def parse_coordinate_value(
    value: str,
    label: str,
    minimum: float,
    maximum: float,
) -> float:
    text = value.strip()
    if not text:
        raise ValueError(f"{label} is required.")

    try:
        parsed = float(text)
    except ValueError as exc:
        raise ValueError(f"{label} must be a valid number.") from exc

    if not minimum <= parsed <= maximum:
        raise ValueError(f"{label} must be in [{minimum}, {maximum}].")

    return parsed


def try_parse_coordinate_pair(
    latitude_text: str,
    longitude_text: str,
) -> tuple[float, float] | None:
    try:
        latitude = parse_coordinate_value(latitude_text, "Latitude", -90.0, 90.0)
        longitude = parse_coordinate_value(longitude_text, "Longitude", -180.0, 180.0)
    except ValueError:
        return None

    return latitude, longitude


def parse_coordinate_text(value: str) -> tuple[float, float] | None:
    latitude_text, separator, longitude_text = value.strip().partition(",")
    if not separator:
        return None

    latitude_candidate = latitude_text.strip()
    longitude_candidate = longitude_text.strip()
    if not _looks_numeric(latitude_candidate) or not _looks_numeric(longitude_candidate):
        return None

    return (
        parse_coordinate_value(latitude_candidate, "Latitude", -90.0, 90.0),
        parse_coordinate_value(longitude_candidate, "Longitude", -180.0, 180.0),
    )


def resolve_location_text(
    value: str,
    geocoder: GeocoderLike,
) -> ResolvedLocationInput:
    query = value.strip()
    if not query:
        raise ValueError("Location is required.")

    coordinate_pair = parse_coordinate_text(query)
    if coordinate_pair is not None:
        return ResolvedLocationInput(
            latitude=coordinate_pair[0],
            longitude=coordinate_pair[1],
            source="coordinates",
            query=query,
        )

    latitude, longitude = geocoder.geocode(query)
    latitude = parse_coordinate_value(str(latitude), "Latitude", -90.0, 90.0)
    longitude = parse_coordinate_value(str(longitude), "Longitude", -180.0, 180.0)
    return ResolvedLocationInput(
        latitude=latitude,
        longitude=longitude,
        source="address",
        query=query,
    )


def format_resolution_feedback(resolved_location: ResolvedLocationInput) -> str:
    latitude_text = f"{resolved_location.latitude:.2f}"
    longitude_text = f"{resolved_location.longitude:.2f}"
    if resolved_location.source == "address":
        return f"Resolved: {resolved_location.query} -> ({latitude_text}, {longitude_text})"
    return f"Resolved coordinates -> ({latitude_text}, {longitude_text})"


def format_resolution_error(endpoint: str, error_message: str) -> str:
    location_label = "Start" if endpoint == "start" else "End"
    return f"{location_label} input error: {error_message}"


def format_coordinate_pair(latitude: float, longitude: float) -> tuple[str, str]:
    return f"{latitude:.6f}", f"{longitude:.6f}"


def _parse_viewport_field(
    payload: dict[str, object],
    key: str,
    minimum: float,
    maximum: float,
) -> float:
    value = float(payload[key])
    if not minimum <= value <= maximum:
        raise ValueError(f"{key} must be in [{minimum}, {maximum}].")
    return value


def _looks_numeric(value: str) -> bool:
    if not value:
        return False

    try:
        float(value)
    except ValueError:
        return False

    return True
