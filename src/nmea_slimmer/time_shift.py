from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .checksum import with_checksum
from .nmea_parser import parse_line

_SECONDS_PER_DAY = 24 * 60 * 60


def _parse_nmea_seconds(value: str) -> float | None:
    if len(value) < 6:
        return None
    try:
        hours = int(value[0:2])
        minutes = int(value[2:4])
        seconds = float(value[4:])
    except ValueError:
        return None
    if not (0 <= hours < 24 and 0 <= minutes < 60 and 0 <= seconds < 60):
        return None
    return hours * 3600 + minutes * 60 + seconds


def _fraction_digits(value: str) -> int:
    if "." not in value:
        return 0
    return len(value.split(".", 1)[1])


def _format_nmea_time(value: datetime, fraction_digits: int) -> str:
    whole_seconds = value.hour * 3600 + value.minute * 60 + value.second
    if fraction_digits == 0:
        return f"{value.hour:02d}{value.minute:02d}{value.second:02d}"
    fraction = f"{value.microsecond:06d}"[:fraction_digits].ljust(fraction_digits, "0")
    return f"{whole_seconds // 3600:02d}{(whole_seconds % 3600) // 60:02d}{whole_seconds % 60:02d}.{fraction}"


def shift_start_datetime(lines: list[str], start_datetime_utc: datetime) -> list[str]:
    """Shift retained RMC/GGA sentences so the first valid timestamp uses the requested UTC time."""
    if start_datetime_utc.tzinfo is None:
        raise ValueError("起始时间必须包含 UTC 时区")
    start_datetime_utc = start_datetime_utc.astimezone(timezone.utc)

    shifted: list[str] = []
    first_seconds: float | None = None
    previous_seconds: float | None = None
    day_offset = 0

    for line in lines:
        parsed = parse_line(line)
        if parsed.sentence_type not in {"RMC", "GGA"}:
            shifted.append(line)
            continue

        fields = parsed.body.split(",")
        if len(fields) < 2:
            shifted.append(line)
            continue
        current_seconds = _parse_nmea_seconds(fields[1])
        if current_seconds is None:
            shifted.append(line)
            continue

        if previous_seconds is not None and current_seconds < previous_seconds - (_SECONDS_PER_DAY / 2):
            day_offset += 1
        absolute_seconds = day_offset * _SECONDS_PER_DAY + current_seconds
        if first_seconds is None:
            first_seconds = absolute_seconds
        previous_seconds = current_seconds

        new_datetime = start_datetime_utc + timedelta(seconds=absolute_seconds - first_seconds)
        fields[1] = _format_nmea_time(new_datetime, _fraction_digits(fields[1]))
        if parsed.sentence_type == "RMC" and len(fields) > 9:
            fields[9] = new_datetime.strftime("%d%m%y")
        shifted.append(with_checksum(",".join(fields)))

    if first_seconds is None:
        raise ValueError("无法设置起始时间：输入文件中没有可识别的 RMC/GGA 时间字段。")
    return shifted
