from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from core.nmea_writer import trackpoint_to_nmea_sentences
from core.track_model import TrackPoint
from generator.models import GeneratedTrackPoint

DEFAULT_START_TIME = datetime(1970, 1, 1, tzinfo=timezone.utc)
DEFAULT_FIX_QUALITY = 1
DEFAULT_NUM_SATS = 8
DEFAULT_HDOP = 0.9
DEFAULT_STATUS = "A"


def generate_nmea_lines(
    points: Iterable[GeneratedTrackPoint],
    *,
    start_time: datetime | None = None,
) -> list[str]:
    lines: list[str] = []
    resolved_start_time = _normalize_start_time(start_time) or DEFAULT_START_TIME
    for point in points:
        timestamp = _resolve_timestamp(point, fallback_start_time=resolved_start_time)
        track_point = generated_point_to_track_point(
            point,
            fallback_start_time=resolved_start_time,
        )
        rmc, gga = trackpoint_to_nmea_sentences(
            track_point,
            date_str=_format_nmea_date(timestamp),
        )
        lines.extend([rmc, gga])
    return lines


def write_nmea_file(
    points: Iterable[GeneratedTrackPoint],
    path: str | Path,
    *,
    start_time: datetime | None = None,
) -> int:
    output_path = Path(path)
    lines = generate_nmea_lines(points, start_time=start_time)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="ascii", newline="") as handle:
        for line in lines:
            handle.write(line)
            handle.write("\r\n")
    return len(lines)


def generated_point_to_track_point(
    point: GeneratedTrackPoint,
    *,
    fallback_start_time: datetime | None = None,
) -> TrackPoint:
    resolved_start_time = _normalize_start_time(fallback_start_time) or DEFAULT_START_TIME
    timestamp = _resolve_timestamp(point, fallback_start_time=resolved_start_time)
    return TrackPoint(
        time_str=_format_nmea_time(timestamp),
        lat=point.lat,
        lon=point.lon,
        alt_m=point.altitude_m,
        speed_knots=point.speed_knots,
        course_deg=point.course_deg,
        fix_quality=DEFAULT_FIX_QUALITY,
        num_sats=DEFAULT_NUM_SATS,
        hdop=DEFAULT_HDOP,
        status=DEFAULT_STATUS,
    )


def _resolve_timestamp(
    point: GeneratedTrackPoint,
    *,
    fallback_start_time: datetime,
) -> datetime:
    if point.timestamp is None:
        return fallback_start_time + timedelta(seconds=point.seconds_from_start)

    timestamp = point.timestamp
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def _normalize_start_time(start_time: datetime | None) -> datetime | None:
    if start_time is None:
        return None
    if start_time.tzinfo is None:
        return start_time.replace(tzinfo=timezone.utc)
    return start_time.astimezone(timezone.utc)


def _format_nmea_time(value: datetime) -> str:
    rounded = value
    centiseconds = int(round(rounded.microsecond / 10_000.0))
    if centiseconds == 100:
        rounded = rounded + timedelta(seconds=1)
        centiseconds = 0
    return f"{rounded:%H%M%S}.{centiseconds:02d}"


def _format_nmea_date(value: datetime) -> str:
    return value.strftime("%d%m%y")
