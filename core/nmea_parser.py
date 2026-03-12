from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from core.track_model import TrackPoint, TrackSegment, TrackSummary


class NMEAParseError(ValueError):
    """Raised when an NMEA sentence cannot be parsed."""


@dataclass(slots=True)
class _SentenceRecord:
    sentence_type: str
    point: TrackPoint


@dataclass(slots=True)
class _PendingPoint:
    time_str: str
    lat: float | None = None
    lon: float | None = None
    alt_m: float | None = None
    speed_knots: float | None = None
    course_deg: float | None = None
    fix_quality: int | None = None
    num_sats: int | None = None
    hdop: float | None = None
    status: str = ""
    has_rmc: bool = False
    has_gga: bool = False

    def apply(self, record: _SentenceRecord) -> None:
        point = record.point
        if self.lat is None:
            self.lat = point.lat
        if self.lon is None:
            self.lon = point.lon
        if self.alt_m is None:
            self.alt_m = point.alt_m
        if self.speed_knots is None:
            self.speed_knots = point.speed_knots
        if self.course_deg is None:
            self.course_deg = point.course_deg
        if self.fix_quality is None:
            self.fix_quality = point.fix_quality
        if self.num_sats is None:
            self.num_sats = point.num_sats
        if self.hdop is None:
            self.hdop = point.hdop
        if not self.status and point.status:
            self.status = point.status

        if record.sentence_type == "RMC":
            self.has_rmc = True
        elif record.sentence_type == "GGA":
            self.has_gga = True

    def to_track_point(self) -> TrackPoint:
        return TrackPoint(
            time_str=self.time_str,
            lat=self.lat,
            lon=self.lon,
            alt_m=self.alt_m,
            speed_knots=self.speed_knots,
            course_deg=self.course_deg,
            fix_quality=self.fix_quality,
            num_sats=self.num_sats,
            hdop=self.hdop,
            status=self.status,
        )


def parse_sentence(sentence: str) -> _SentenceRecord | None:
    sentence_type, fields = _split_sentence(sentence)
    if sentence_type == "GPRMC":
        return _SentenceRecord("RMC", parse_gprmc_fields(fields))
    if sentence_type == "GPGGA":
        return _SentenceRecord("GGA", parse_gpgga_fields(fields))
    return None


def parse_gprmc(sentence: str) -> TrackPoint:
    sentence_type, fields = _split_sentence(sentence)
    if sentence_type != "GPRMC":
        raise NMEAParseError(f"Expected GPRMC sentence, got {sentence_type}.")
    return parse_gprmc_fields(fields)


def parse_gpgga(sentence: str) -> TrackPoint:
    sentence_type, fields = _split_sentence(sentence)
    if sentence_type != "GPGGA":
        raise NMEAParseError(f"Expected GPGGA sentence, got {sentence_type}.")
    return parse_gpgga_fields(fields)


def parse_gprmc_fields(fields: list[str]) -> TrackPoint:
    if len(fields) < 10:
        raise NMEAParseError("GPRMC sentence is missing required fields.")

    time_str = fields[1]
    if not time_str:
        raise NMEAParseError("GPRMC sentence is missing the UTC time field.")

    return TrackPoint(
        time_str=time_str,
        lat=_parse_coordinate(fields[3], fields[4], is_latitude=True),
        lon=_parse_coordinate(fields[5], fields[6], is_latitude=False),
        speed_knots=_parse_float(fields[7]),
        course_deg=_parse_float(fields[8]),
        status=fields[2].upper(),
    )


def parse_gpgga_fields(fields: list[str]) -> TrackPoint:
    if len(fields) < 10:
        raise NMEAParseError("GPGGA sentence is missing required fields.")

    time_str = fields[1]
    if not time_str:
        raise NMEAParseError("GPGGA sentence is missing the UTC time field.")

    return TrackPoint(
        time_str=time_str,
        lat=_parse_coordinate(fields[2], fields[3], is_latitude=True),
        lon=_parse_coordinate(fields[4], fields[5], is_latitude=False),
        alt_m=_parse_float(fields[9]),
        fix_quality=_parse_int(fields[6]),
        num_sats=_parse_int(fields[7]),
        hdop=_parse_float(fields[8]),
    )


def merge_sentence_records(records: Iterable[_SentenceRecord]) -> list[TrackPoint]:
    merged: list[_PendingPoint] = []
    pending_by_time: dict[str, list[int]] = {}

    for record in records:
        time_key = record.point.time_str
        pending_indexes = pending_by_time.setdefault(time_key, [])
        target_index: int | None = None

        for index in pending_indexes:
            pending = merged[index]
            if record.sentence_type == "RMC" and not pending.has_rmc:
                target_index = index
                break
            if record.sentence_type == "GGA" and not pending.has_gga:
                target_index = index
                break

        if target_index is None:
            target_index = len(merged)
            merged.append(_PendingPoint(time_str=time_key))
            pending_indexes.append(target_index)

        merged[target_index].apply(record)

        pending = merged[target_index]
        if pending.has_rmc and pending.has_gga:
            pending_indexes.remove(target_index)
            if not pending_indexes:
                pending_by_time.pop(time_key, None)

    return [pending.to_track_point() for pending in merged]


def parse_nmea_lines(lines: Iterable[str]) -> list[TrackPoint]:
    records: list[_SentenceRecord] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        record = parse_sentence(line)
        if record is not None:
            records.append(record)
    return merge_sentence_records(records)


def parse_nmea_file(path: str | Path) -> list[TrackPoint]:
    input_path = Path(path)
    with input_path.open("r", encoding="ascii", newline="") as handle:
        return parse_nmea_lines(handle)


def process_nmea_lines(
    lines: Iterable[str],
    *,
    max_speed_kmh: float = 300.0,
    split_gap_seconds: float = 10.0,
) -> tuple[list[TrackPoint], list[TrackSegment], TrackSummary]:
    from core.pipeline import build_track_from_lines

    result = build_track_from_lines(
        lines,
        max_speed_kmh=max_speed_kmh,
        split_gap_seconds=split_gap_seconds,
    )
    return result.points, result.segments, result.summary


def process_nmea_file(
    path: str | Path,
    *,
    max_speed_kmh: float = 300.0,
    split_gap_seconds: float = 10.0,
) -> tuple[list[TrackPoint], list[TrackSegment], TrackSummary]:
    from core.pipeline import build_track_from_file

    result = build_track_from_file(
        path,
        max_speed_kmh=max_speed_kmh,
        split_gap_seconds=split_gap_seconds,
    )
    return result.points, result.segments, result.summary


def _split_sentence(sentence: str) -> tuple[str, list[str]]:
    line = sentence.strip()
    if not line:
        raise NMEAParseError("NMEA sentence is empty.")
    if not line.startswith("$"):
        raise NMEAParseError("NMEA sentence must start with '$'.")

    if "*" in line:
        payload, checksum_text = line[1:].split("*", 1)
        expected = _checksum(payload)
        if checksum_text.upper() != f"{expected:02X}":
            raise NMEAParseError(
                f"Invalid checksum for sentence: expected {expected:02X}, got {checksum_text}."
            )
    else:
        payload = line[1:]

    fields = payload.split(",")
    return fields[0], fields


def _checksum(payload: str) -> int:
    checksum = 0
    for character in payload:
        checksum ^= ord(character)
    return checksum


def _parse_coordinate(value: str, hemisphere: str, *, is_latitude: bool) -> float | None:
    if not value or not hemisphere:
        return None

    degree_digits = 2 if is_latitude else 3
    if len(value) < degree_digits:
        raise NMEAParseError(f"Invalid coordinate field: {value}")

    try:
        degrees = int(value[:degree_digits])
        minutes = float(value[degree_digits:])
    except ValueError as exc:
        raise NMEAParseError(f"Invalid coordinate field: {value}") from exc

    decimal_degrees = degrees + minutes / 60.0
    hemisphere = hemisphere.upper()
    if hemisphere in {"S", "W"}:
        decimal_degrees = -decimal_degrees
    elif hemisphere not in {"N", "E"}:
        raise NMEAParseError(f"Invalid coordinate hemisphere: {hemisphere}")

    if is_latitude and not -90.0 <= decimal_degrees <= 90.0:
        raise NMEAParseError(f"Latitude out of range: {decimal_degrees}")
    if not is_latitude and not -180.0 <= decimal_degrees <= 180.0:
        raise NMEAParseError(f"Longitude out of range: {decimal_degrees}")

    return decimal_degrees


def _parse_float(value: str) -> float | None:
    if value == "":
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise NMEAParseError(f"Invalid float field: {value}") from exc


def _parse_int(value: str) -> int | None:
    if value == "":
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise NMEAParseError(f"Invalid integer field: {value}") from exc
