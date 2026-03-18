from __future__ import annotations

import json

from core.geo import calc_speed_kmh, haversine_m
from core.pipeline import TrackResult
from core.track_model import TrackPoint, TrackSegment, TrackSummary, time_str_to_seconds

LOW_SPEED_COLOR = (32, 105, 211)
HIGH_SPEED_COLOR = (215, 38, 61)

TABLE_COLUMNS = [
    ("time_str", "time_str"),
    ("lat", "lat"),
    ("lon", "lon"),
    ("alt_m", "alt_m"),
    ("speed_knots", "speed_knots"),
    ("course_deg", "course_deg"),
    ("fix_quality", "fix_quality"),
    ("num_sats", "num_sats"),
    ("hdop", "hdop"),
    ("is_valid", "is_valid"),
    ("invalid_reason", "invalid_reason"),
    ("anomalies", "anomaly_flags"),
]

SUMMARY_FIELDS = [
    ("Total points", "total_points"),
    ("Valid points", "valid_points"),
    ("Invalid points", "invalid_points"),
    ("Segment count", "segment_count"),
    ("Total distance (meters)", "total_distance_m"),
    ("Duration (seconds)", "duration_seconds"),
    ("Average speed (km/h)", "avg_speed_kmh"),
    ("Max speed (km/h)", "max_speed_kmh"),
]


def build_summary_rows(summary: TrackSummary) -> list[tuple[str, str]]:
    return [
        ("Total points", str(summary.total_points)),
        ("Valid points", str(summary.valid_points)),
        ("Invalid points", str(summary.invalid_points)),
        ("Segment count", str(summary.segment_count)),
        ("Total distance (meters)", f"{summary.total_distance_m:.2f}"),
        ("Duration (seconds)", f"{summary.duration_seconds:.2f}"),
        ("Average speed (km/h)", f"{summary.avg_speed_kmh:.2f}"),
        ("Max speed (km/h)", f"{summary.max_speed_kmh:.2f}"),
    ]


def track_point_to_row_values(
    point: TrackPoint,
    *,
    use_smoothed_coordinates: bool = False,
) -> list[str]:
    lat, lon = point.coordinates(use_smoothed=use_smoothed_coordinates)

    return [
        point.time_str,
        format_value(lat, decimals=6),
        format_value(lon, decimals=6),
        format_value(point.alt_m, decimals=1),
        format_value(point.speed_knots, decimals=2),
        format_value(point.course_deg, decimals=2),
        format_value(point.fix_quality),
        format_value(point.num_sats),
        format_value(point.hdop, decimals=1),
        "True" if point.is_valid else "False",
        point.invalid_reason,
        "; ".join(point.anomaly_flags),
    ]


def format_value(value: object, decimals: int | None = None) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and decimals is not None:
        return f"{value:.{decimals}f}"
    return str(value)


def build_map_payload(
    result: TrackResult | None,
    *,
    use_smoothed_coordinates: bool = False,
    color_by_speed: bool = False,
) -> dict[str, object]:
    if result is None:
        return {
            "polylines": [],
            "speed_polylines": [],
            "invalid_points": [],
            "anomaly_points": [],
            "start_point": None,
            "end_point": None,
            "color_by_speed": color_by_speed,
        }

    polylines: list[list[list[float]]] = []
    speed_polylines = (
        _build_speed_polylines(
            result.segments,
            use_smoothed_coordinates=use_smoothed_coordinates,
        )
        if color_by_speed
        else []
    )
    start_point: dict[str, float] | None = None
    end_point: dict[str, float] | None = None
    invalid_points: list[dict[str, object]] = []
    anomaly_points: list[dict[str, object]] = []

    for segment in result.segments:
        segment_line: list[list[float]] = []
        for point in segment.points:
            coordinates = _coordinates_or_none(
                point,
                use_smoothed_coordinates=use_smoothed_coordinates,
            )
            if coordinates is None:
                continue

            lat, lon = coordinates
            coordinate = [lat, lon]

            if point.is_valid:
                segment_line.append(coordinate)
                marker = {
                    "lat": lat,
                    "lon": lon,
                    "time_str": point.time_str,
                }
                if start_point is None:
                    start_point = marker
                end_point = marker
            elif not point.anomaly_flags:
                invalid_points.append(
                    {
                        "lat": lat,
                        "lon": lon,
                        "time_str": point.time_str,
                        "reason": point.invalid_reason,
                    }
                )

            if point.anomaly_flags:
                anomaly_points.append(
                    {
                        "lat": lat,
                        "lon": lon,
                        "time_str": point.time_str,
                        "reason": "; ".join(point.anomaly_flags),
                        "details": point.invalid_reason,
                    }
                )

        if len(segment_line) >= 2:
            polylines.append(segment_line)

    if start_point is None or end_point is None:
        valid_points = [
            point
            for point in result.points
            if point.is_valid
            and _coordinates_or_none(
                point,
                use_smoothed_coordinates=use_smoothed_coordinates,
            )
            is not None
        ]
        if valid_points:
            start_lat, start_lon = _coordinates_or_none(
                valid_points[0],
                use_smoothed_coordinates=use_smoothed_coordinates,
            )
            end_lat, end_lon = _coordinates_or_none(
                valid_points[-1],
                use_smoothed_coordinates=use_smoothed_coordinates,
            )
            start_point = {
                "lat": start_lat,
                "lon": start_lon,
                "time_str": valid_points[0].time_str,
            }
            end_point = {
                "lat": end_lat,
                "lon": end_lon,
                "time_str": valid_points[-1].time_str,
            }

    return {
        "polylines": polylines,
        "speed_polylines": speed_polylines,
        "invalid_points": invalid_points,
        "anomaly_points": anomaly_points,
        "start_point": start_point,
        "end_point": end_point,
        "color_by_speed": color_by_speed,
    }


def build_map_html(
    result: TrackResult | None,
    *,
    use_smoothed_coordinates: bool = False,
    color_by_speed: bool = False,
) -> str:
    payload = build_map_payload(
        result,
        use_smoothed_coordinates=use_smoothed_coordinates,
        color_by_speed=color_by_speed,
    )
    payload_json = json.dumps(payload, separators=(",", ":"))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>NMEA Track Map</title>
  <link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
    crossorigin=""
  >
  <style>
    html, body, #map {{
      height: 100%;
      margin: 0;
      padding: 0;
      background: #f4f1eb;
    }}
    .leaflet-container {{
      font-family: "Segoe UI", sans-serif;
    }}
    .map-empty {{
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100%;
      color: #5c5f52;
      font-size: 14px;
      letter-spacing: 0.02em;
    }}
  </style>
</head>
<body>
  <div id="map"></div>
  <script
    src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
    crossorigin=""
  ></script>
  <script>
    const trackData = {payload_json};
    const mapElement = document.getElementById("map");

    if (!window.L) {{
      mapElement.innerHTML = '<div class="map-empty">Leaflet failed to load.</div>';
    }} else if (
      trackData.polylines.length === 0 &&
      trackData.speed_polylines.length === 0 &&
      trackData.invalid_points.length === 0 &&
      trackData.anomaly_points.length === 0 &&
      !trackData.start_point &&
      !trackData.end_point
    ) {{
      mapElement.innerHTML = '<div class="map-empty">Open an NMEA file to view the track.</div>';
    }} else {{
      const map = L.map("map", {{
        zoomControl: true,
        preferCanvas: true
      }});

      L.tileLayer("https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap contributors"
      }}).addTo(map);

      const bounds = [];

      if (trackData.color_by_speed && trackData.speed_polylines.length > 0) {{
        for (const segment of trackData.speed_polylines) {{
          const polyline = L.polyline(segment.line, {{
            color: segment.color,
            weight: 5,
            opacity: 0.95,
            lineCap: "round",
            lineJoin: "round"
          }}).addTo(map);
          bounds.push(...polyline.getLatLngs());
        }}
      }} else {{
        for (const line of trackData.polylines) {{
          const polyline = L.polyline(line, {{
            color: "#1f6f78",
            weight: 4,
            opacity: 0.9
          }}).addTo(map);
          bounds.push(...polyline.getLatLngs());
        }}
      }}

      for (const point of trackData.invalid_points) {{
        const marker = L.circleMarker([point.lat, point.lon], {{
          radius: 6,
          color: "#9f1d35",
          fillColor: "#d7263d",
          fillOpacity: 0.95,
          weight: 2
        }}).addTo(map);
        marker.bindPopup(`<strong>Invalid Point</strong><br>${{point.time_str}}<br>${{point.reason || ""}}`);
        bounds.push(marker.getLatLng());
      }}

      for (const point of trackData.anomaly_points) {{
        const detailLine = point.details ? `<br>${{point.details}}` : "";
        const marker = L.circleMarker([point.lat, point.lon], {{
          radius: 7,
          color: "#8b0000",
          fillColor: "#ff3b30",
          fillOpacity: 0.98,
          weight: 2
        }}).addTo(map);
        marker.bindPopup(
          `<strong>Anomaly Point</strong><br>${{point.time_str}}<br>${{point.reason || ""}}${{detailLine}}`
        );
        bounds.push(marker.getLatLng());
      }}

      if (trackData.start_point) {{
        const marker = L.circleMarker([trackData.start_point.lat, trackData.start_point.lon], {{
          radius: 7,
          color: "#1a4d2e",
          fillColor: "#2a9d5b",
          fillOpacity: 0.95,
          weight: 2
        }}).addTo(map);
        marker.bindPopup(`<strong>Start</strong><br>${{trackData.start_point.time_str}}`);
        bounds.push(marker.getLatLng());
      }}

      if (trackData.end_point) {{
        const marker = L.circleMarker([trackData.end_point.lat, trackData.end_point.lon], {{
          radius: 7,
          color: "#7f4f24",
          fillColor: "#f4a261",
          fillOpacity: 0.95,
          weight: 2
        }}).addTo(map);
        marker.bindPopup(`<strong>End</strong><br>${{trackData.end_point.time_str}}`);
        bounds.push(marker.getLatLng());
      }}

      if (bounds.length > 0) {{
        map.fitBounds(L.latLngBounds(bounds), {{
          padding: [20, 20]
        }});
      }} else {{
        map.setView([0, 0], 2);
      }}
    }}
  </script>
</body>
</html>"""


def _build_speed_polylines(
    segments: list[TrackSegment],
    *,
    use_smoothed_coordinates: bool,
) -> list[dict[str, object]]:
    speed_polylines: list[dict[str, object]] = []

    for segment in segments:
        previous_point: TrackPoint | None = None
        previous_time_seconds: float | None = None
        previous_coordinates: tuple[float, float] | None = None

        for point in segment.points:
            current_time_seconds = _time_seconds_or_none(point)
            current_coordinates = _coordinates_or_none(
                point,
                use_smoothed_coordinates=use_smoothed_coordinates,
            )

            if not point.is_valid or current_time_seconds is None or current_coordinates is None:
                previous_point = None
                previous_time_seconds = None
                previous_coordinates = None
                continue

            if (
                previous_point is not None
                and previous_time_seconds is not None
                and previous_coordinates is not None
            ):
                delta_seconds = current_time_seconds - previous_time_seconds
                if delta_seconds > 0.0:
                    distance_m = haversine_m(
                        previous_coordinates[0],
                        previous_coordinates[1],
                        current_coordinates[0],
                        current_coordinates[1],
                    )
                    speed_kmh = (
                        point.calculated_speed_kmh
                        if not use_smoothed_coordinates and point.calculated_speed_kmh is not None
                        else calc_speed_kmh(distance_m, delta_seconds)
                    )
                    speed_polylines.append(
                        {
                            "line": [
                                [previous_coordinates[0], previous_coordinates[1]],
                                [current_coordinates[0], current_coordinates[1]],
                            ],
                            "speed_kmh": speed_kmh,
                        }
                    )

            previous_point = point
            previous_time_seconds = current_time_seconds
            previous_coordinates = current_coordinates

    if not speed_polylines:
        return []

    max_speed_kmh = max(polyline["speed_kmh"] for polyline in speed_polylines)
    max_speed_kmh = max(max_speed_kmh, 1.0)

    for polyline in speed_polylines:
        polyline["color"] = _speed_to_color(polyline["speed_kmh"], max_speed_kmh)

    return speed_polylines


def _speed_to_color(speed_kmh: float, max_speed_kmh: float) -> str:
    clamped_ratio = min(max(speed_kmh / max_speed_kmh, 0.0), 1.0)
    red = round(LOW_SPEED_COLOR[0] + (HIGH_SPEED_COLOR[0] - LOW_SPEED_COLOR[0]) * clamped_ratio)
    green = round(
        LOW_SPEED_COLOR[1] + (HIGH_SPEED_COLOR[1] - LOW_SPEED_COLOR[1]) * clamped_ratio
    )
    blue = round(LOW_SPEED_COLOR[2] + (HIGH_SPEED_COLOR[2] - LOW_SPEED_COLOR[2]) * clamped_ratio)
    return f"#{red:02x}{green:02x}{blue:02x}"


def _coordinates_or_none(
    point: TrackPoint,
    *,
    use_smoothed_coordinates: bool,
) -> tuple[float, float] | None:
    lat, lon = point.coordinates(use_smoothed=use_smoothed_coordinates)
    if lat is None or lon is None:
        return None
    return lat, lon


def _time_seconds_or_none(point: TrackPoint) -> float | None:
    try:
        return time_str_to_seconds(point.time_str)
    except ValueError:
        return None
