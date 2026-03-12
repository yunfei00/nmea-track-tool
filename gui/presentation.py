from __future__ import annotations

import json

from core.pipeline import TrackResult
from core.track_model import TrackPoint, TrackSummary

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


def track_point_to_row_values(point: TrackPoint) -> list[str]:
    return [
        point.time_str,
        format_value(point.lat, decimals=6),
        format_value(point.lon, decimals=6),
        format_value(point.alt_m, decimals=1),
        format_value(point.speed_knots, decimals=2),
        format_value(point.course_deg, decimals=2),
        format_value(point.fix_quality),
        format_value(point.num_sats),
        format_value(point.hdop, decimals=1),
        "True" if point.is_valid else "False",
        point.invalid_reason,
    ]


def format_value(value: object, decimals: int | None = None) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and decimals is not None:
        return f"{value:.{decimals}f}"
    return str(value)


def build_map_payload(result: TrackResult | None) -> dict[str, object]:
    if result is None:
        return {
            "polylines": [],
            "invalid_points": [],
            "start_point": None,
            "end_point": None,
        }

    polylines: list[list[list[float]]] = []
    start_point: dict[str, float] | None = None
    end_point: dict[str, float] | None = None
    invalid_points: list[dict[str, object]] = []

    for segment in result.segments:
        segment_line: list[list[float]] = []
        for point in segment.points:
            if point.lat is None or point.lon is None:
                continue

            coordinate = [point.lat, point.lon]

            if point.is_valid:
                segment_line.append(coordinate)
                marker = {
                    "lat": point.lat,
                    "lon": point.lon,
                    "time_str": point.time_str,
                }
                if start_point is None:
                    start_point = marker
                end_point = marker
            else:
                invalid_points.append(
                    {
                        "lat": point.lat,
                        "lon": point.lon,
                        "time_str": point.time_str,
                        "reason": point.invalid_reason,
                    }
                )

        if len(segment_line) >= 2:
            polylines.append(segment_line)

    if start_point is None or end_point is None:
        valid_points = [
            point
            for point in result.points
            if point.is_valid and point.lat is not None and point.lon is not None
        ]
        if valid_points:
            start_point = {
                "lat": valid_points[0].lat,
                "lon": valid_points[0].lon,
                "time_str": valid_points[0].time_str,
            }
            end_point = {
                "lat": valid_points[-1].lat,
                "lon": valid_points[-1].lon,
                "time_str": valid_points[-1].time_str,
            }

    return {
        "polylines": polylines,
        "invalid_points": invalid_points,
        "start_point": start_point,
        "end_point": end_point,
    }


def build_map_html(result: TrackResult | None) -> str:
    payload = build_map_payload(result)
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
      trackData.invalid_points.length === 0 &&
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

      for (const line of trackData.polylines) {{
        const polyline = L.polyline(line, {{
          color: "#1f6f78",
          weight: 4,
          opacity: 0.9
        }}).addTo(map);
        bounds.push(...polyline.getLatLngs());
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
