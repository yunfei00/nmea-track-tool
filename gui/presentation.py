from __future__ import annotations

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
