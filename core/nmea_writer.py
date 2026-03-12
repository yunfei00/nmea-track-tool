from __future__ import annotations

from pathlib import Path
from typing import Iterable

from core.track_model import TrackPoint


def trackpoint_to_nmea_sentences(
    point: TrackPoint,
    *,
    date_str: str = "",
    magnetic_variation: str = "",
    magnetic_variation_direction: str = "",
) -> tuple[str, str]:
    if point.lat is None or point.lon is None:
        raise ValueError("TrackPoint lat and lon are required to write NMEA sentences.")
    if not -90.0 <= point.lat <= 90.0:
        raise ValueError(f"TrackPoint lat must be in [-90, 90], got {point.lat}.")
    if not -180.0 <= point.lon <= 180.0:
        raise ValueError(f"TrackPoint lon must be in [-180, 180], got {point.lon}.")

    rmc_body = ",".join(
        [
            "GPRMC",
            point.time_str,
            _resolve_status(point),
            *_format_latitude(point.lat),
            *_format_longitude(point.lon),
            _format_float(point.speed_knots, decimals=2),
            _format_float(point.course_deg, decimals=2),
            date_str,
            magnetic_variation,
            magnetic_variation_direction,
        ]
    )
    gga_body = ",".join(
        [
            "GPGGA",
            point.time_str,
            *_format_latitude(point.lat),
            *_format_longitude(point.lon),
            _format_int(point.fix_quality, default=0),
            _format_int(point.num_sats, width=2, default=0),
            _format_float(point.hdop, decimals=1),
            _format_float(point.alt_m, decimals=1),
            "M",
            "",
            "M",
            "",
            "",
        ]
    )
    return _with_checksum(rmc_body), _with_checksum(gga_body)


def write_nmea_lines(points: Iterable[TrackPoint], *, date_str: str = "") -> list[str]:
    lines: list[str] = []
    for point in points:
        rmc, gga = trackpoint_to_nmea_sentences(point, date_str=date_str)
        lines.extend([rmc, gga])
    return lines


def write_nmea_file(points: Iterable[TrackPoint], path: str | Path, *, date_str: str = "") -> int:
    output_path = Path(path)
    lines = write_nmea_lines(points, date_str=date_str)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="ascii", newline="") as handle:
        for line in lines:
            handle.write(line)
            handle.write("\r\n")
    return len(lines)


def _resolve_status(point: TrackPoint) -> str:
    if point.status:
        return point.status.upper()
    if point.fix_quality is not None and point.fix_quality > 0:
        return "A"
    return "V"


def _format_latitude(latitude: float) -> tuple[str, str]:
    hemisphere = "N" if latitude >= 0 else "S"
    absolute = abs(latitude)
    degrees = int(absolute)
    minutes = (absolute - degrees) * 60.0
    return f"{degrees:02d}{minutes:07.4f}", hemisphere


def _format_longitude(longitude: float) -> tuple[str, str]:
    hemisphere = "E" if longitude >= 0 else "W"
    absolute = abs(longitude)
    degrees = int(absolute)
    minutes = (absolute - degrees) * 60.0
    return f"{degrees:03d}{minutes:07.4f}", hemisphere


def _format_float(value: float | None, *, decimals: int) -> str:
    if value is None:
        return ""
    return f"{value:.{decimals}f}"


def _format_int(value: int | None, *, default: int | None = None, width: int = 0) -> str:
    if value is None:
        if default is None:
            return ""
        value = default
    if width:
        return f"{value:0{width}d}"
    return str(value)


def _with_checksum(payload: str) -> str:
    checksum = 0
    for character in payload:
        checksum ^= ord(character)
    return f"${payload}*{checksum:02X}"
