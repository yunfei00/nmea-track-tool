from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass(slots=True)
class TrackPoint:
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
    is_valid: bool = True
    invalid_reason: str = ""
    calculated_speed_kmh: float | None = None
    anomaly_flags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.time_str:
            raise ValueError("time_str must not be empty.")

        if self.status:
            self.status = self.status.upper()

        if self.invalid_reason:
            self.is_valid = False

        self.anomaly_flags = _normalize_text_flags(self.anomaly_flags)

    def set_invalid(self, reason: str) -> None:
        clean_reason = reason.strip()
        if not clean_reason:
            return

        self.is_valid = False
        if not self.invalid_reason:
            self.invalid_reason = clean_reason
            return

        existing_reasons = {
            existing.strip().lower()
            for existing in self.invalid_reason.split(";")
            if existing.strip()
        }
        if clean_reason.lower() not in existing_reasons:
            self.invalid_reason = f"{self.invalid_reason}; {clean_reason}"

    def add_anomaly_flag(self, flag: str) -> None:
        self.anomaly_flags = _normalize_text_flags([*self.anomaly_flags, flag])

    def clear_anomaly_flags(self) -> None:
        self.anomaly_flags = []


@dataclass(slots=True)
class TrackSegment:
    points: list[TrackPoint]

    def __post_init__(self) -> None:
        if not self.points:
            raise ValueError("TrackSegment must contain at least one TrackPoint.")


@dataclass(slots=True)
class TrackSummary:
    total_points: int
    valid_points: int
    invalid_points: int
    segment_count: int
    total_distance_m: float
    duration_seconds: float
    max_speed_kmh: float
    avg_speed_kmh: float


def clone_track_point(point: TrackPoint) -> TrackPoint:
    return replace(point, anomaly_flags=list(point.anomaly_flags))


def time_str_to_seconds(time_str: str) -> float:
    if not time_str:
        raise ValueError("time_str must not be empty.")

    base, _, fraction = time_str.partition(".")
    if len(base) != 6 or not base.isdigit():
        raise ValueError(f"Invalid NMEA time string: {time_str}")

    hours = int(base[0:2])
    minutes = int(base[2:4])
    seconds = int(base[4:6])
    fractional_seconds = float(f"0.{fraction}") if fraction else 0.0

    if not 0 <= hours <= 23:
        raise ValueError(f"Invalid hour value in time_str: {time_str}")
    if not 0 <= minutes <= 59:
        raise ValueError(f"Invalid minute value in time_str: {time_str}")
    if not 0 <= seconds <= 59:
        raise ValueError(f"Invalid second value in time_str: {time_str}")

    return hours * 3600.0 + minutes * 60.0 + seconds + fractional_seconds


def _normalize_text_flags(flags: list[str]) -> list[str]:
    normalized_flags: list[str] = []
    seen_flags: set[str] = set()

    for flag in flags:
        clean_flag = str(flag).strip()
        if not clean_flag:
            continue

        normalized_key = clean_flag.lower()
        if normalized_key in seen_flags:
            continue

        seen_flags.add(normalized_key)
        normalized_flags.append(clean_flag)

    return normalized_flags
