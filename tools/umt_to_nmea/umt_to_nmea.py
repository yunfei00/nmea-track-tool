from __future__ import annotations

import argparse
import csv
import logging
import math
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

EARTH_RADIUS_M = 6_371_000.0
MPS_TO_KNOTS = 1.9438444924406
DEFAULT_START_DATETIME = datetime(1970, 1, 1, tzinfo=timezone.utc)
COORDINATE_EPSILON = 1e-9


class ConverterError(Exception):
    """Raised when the UMT to NMEA conversion cannot continue."""


@dataclass(frozen=True)
class UMTPoint:
    relative_time_s: float
    latitude_raw: float
    longitude_raw: float
    altitude_m: float


@dataclass(frozen=True)
class GeoPoint:
    relative_time_s: float
    latitude_deg: float
    longitude_deg: float
    altitude_m: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a UMT track file into NMEA 0183 GPRMC/GPGGA sentences.",
    )
    parser.add_argument("input", type=Path, help="Path to the input .umt file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Path to the output .nmea file",
    )
    parser.add_argument(
        "--start-datetime",
        type=parse_start_datetime,
        help="UTC start datetime in ISO 8601 format, for example 2026-03-12T00:00:00Z",
    )
    parser.add_argument(
        "--time-start",
        type=float,
        help="Inclusive lower bound for the relative time filter, in seconds",
    )
    parser.add_argument(
        "--time-end",
        type=float,
        help="Inclusive upper bound for the relative time filter, in seconds",
    )
    parser.add_argument(
        "--sample-step",
        type=parse_sample_step,
        default=1,
        help="Only keep every Nth input row after time filtering. Default: 1",
    )
    return parser.parse_args()


def parse_start_datetime(value: str) -> datetime:
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Invalid --start-datetime. Use ISO 8601, for example "
            "2026-03-12T00:00:00Z."
        ) from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)

    return parsed


def parse_sample_step(value: str) -> int:
    try:
        sample_step = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--sample-step must be a positive integer.") from exc

    if sample_step <= 0:
        raise argparse.ArgumentTypeError("--sample-step must be a positive integer.")

    return sample_step


def load_umt_points(input_path: Path) -> list[UMTPoint]:
    if not input_path.is_file():
        raise ConverterError(f"Input file not found: {input_path}")

    points: list[UMTPoint] = []
    with input_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        for line_number, row in enumerate(reader, start=1):
            if not row or all(not cell.strip() for cell in row):
                continue

            first_cell = row[0].strip()
            if first_cell.startswith("#"):
                continue

            if len(row) <= 5:
                raise ConverterError(
                    f"Line {line_number}: expected at least 6 columns, found {len(row)}."
                )

            try:
                point = UMTPoint(
                    relative_time_s=float(row[0].strip()),
                    latitude_raw=float(row[3].strip()),
                    longitude_raw=float(row[4].strip()),
                    altitude_m=float(row[5].strip()),
                )
            except ValueError as exc:
                raise ConverterError(
                    f"Line {line_number}: could not parse column 0, 3, 4, or 5 as a float."
                ) from exc

            points.append(point)

    if not points:
        raise ConverterError(f"No usable data rows found in {input_path}.")

    return points


def filter_points(
    points: list[UMTPoint],
    time_start: float | None,
    time_end: float | None,
) -> list[UMTPoint]:
    if time_start is not None and time_end is not None and time_start > time_end:
        raise ConverterError("--time-start cannot be greater than --time-end.")

    filtered = [
        point
        for point in points
        if (time_start is None or point.relative_time_s >= time_start)
        and (time_end is None or point.relative_time_s <= time_end)
    ]

    if not filtered:
        raise ConverterError("No rows remain after applying the time filter.")

    return filtered


def sample_points(points: list[UMTPoint], sample_step: int) -> list[UMTPoint]:
    sampled = points[::sample_step]
    if not sampled:
        raise ConverterError("No rows remain after applying --sample-step.")
    return sampled


def detect_coordinate_unit(points: list[UMTPoint]) -> str:
    max_lat = max(abs(point.latitude_raw) for point in points)
    max_lon = max(abs(point.longitude_raw) for point in points)

    if max_lat > 90.0 + COORDINATE_EPSILON or max_lon > 180.0 + COORDINATE_EPSILON:
        raise ConverterError(
            "Input coordinates exceed valid latitude/longitude ranges."
        )

    within_radian_range = (
        max_lat <= math.pi / 2 + COORDINATE_EPSILON
        and max_lon <= math.pi + COORDINATE_EPSILON
    )
    if not within_radian_range:
        return "degrees"

    radians_speed = estimate_median_pair_speed(points, "radians")
    degrees_speed = estimate_median_pair_speed(points, "degrees")
    logging.info(
        "Coordinate unit check: median speed if radians=%.3f m/s, if degrees=%.3f m/s",
        radians_speed,
        degrees_speed,
    )

    radians_plausible = 0.5 <= radians_speed <= 120.0
    degrees_plausible = 0.5 <= degrees_speed <= 120.0

    if radians_plausible and not degrees_plausible:
        logging.info(
            "Coordinate values fit both unit ranges; choosing radians based on motion."
        )
        return "radians"

    if degrees_plausible and not radians_plausible:
        logging.info(
            "Coordinate values fit both unit ranges; choosing degrees based on motion."
        )
        return "degrees"

    logging.warning(
        "Coordinate values fit both degree and radian ranges; defaulting to radians."
    )
    return "radians"


def estimate_median_pair_speed(points: list[UMTPoint], unit: str) -> float:
    speeds: list[float] = []
    for first, second in zip(points, points[1:]):
        delta_t = second.relative_time_s - first.relative_time_s
        if delta_t <= 0:
            continue

        first_lat, first_lon = normalize_coordinates(
            first.latitude_raw,
            first.longitude_raw,
            unit,
        )
        second_lat, second_lon = normalize_coordinates(
            second.latitude_raw,
            second.longitude_raw,
            unit,
        )
        distance_m, _ = distance_and_course(
            first_lat,
            first_lon,
            second_lat,
            second_lon,
        )
        speeds.append(distance_m / delta_t)

    if not speeds:
        return 0.0

    return statistics.median(speeds)


def normalize_coordinates(latitude: float, longitude: float, unit: str) -> tuple[float, float]:
    if unit == "radians":
        latitude = math.degrees(latitude)
        longitude = math.degrees(longitude)

    if not -90.0 <= latitude <= 90.0:
        raise ConverterError(
            f"Latitude out of range after conversion; expected [-90, 90], got {latitude}."
        )
    if not -180.0 <= longitude <= 180.0:
        raise ConverterError(
            f"Longitude out of range after conversion; expected [-180, 180], got {longitude}."
        )

    return latitude, longitude


def convert_points(points: list[UMTPoint], unit: str) -> list[GeoPoint]:
    converted: list[GeoPoint] = []
    for point in points:
        latitude_deg, longitude_deg = normalize_coordinates(
            point.latitude_raw,
            point.longitude_raw,
            unit,
        )
        converted.append(
            GeoPoint(
                relative_time_s=point.relative_time_s,
                latitude_deg=latitude_deg,
                longitude_deg=longitude_deg,
                altitude_m=point.altitude_m,
            )
        )
    return converted


def estimate_speed_and_course(points: list[GeoPoint]) -> list[tuple[float, float]]:
    if len(points) == 1:
        return [(0.0, 0.0)]

    estimates: list[tuple[float, float]] = []
    last_index = len(points) - 1

    for index in range(len(points)):
        if index == 0:
            first = points[0]
            second = points[1]
        elif index == last_index:
            first = points[last_index - 1]
            second = points[last_index]
        else:
            first = points[index - 1]
            second = points[index + 1]

        delta_t = second.relative_time_s - first.relative_time_s
        if delta_t <= 0:
            estimates.append((0.0, 0.0))
            continue

        distance_m, course_deg = distance_and_course(
            first.latitude_deg,
            first.longitude_deg,
            second.latitude_deg,
            second.longitude_deg,
        )
        speed_knots = (distance_m / delta_t) * MPS_TO_KNOTS
        if distance_m <= 0.0:
            course_deg = 0.0
        estimates.append((speed_knots, course_deg))

    return estimates


def distance_and_course(
    latitude1_deg: float,
    longitude1_deg: float,
    latitude2_deg: float,
    longitude2_deg: float,
) -> tuple[float, float]:
    latitude1 = math.radians(latitude1_deg)
    longitude1 = math.radians(longitude1_deg)
    latitude2 = math.radians(latitude2_deg)
    longitude2 = math.radians(longitude2_deg)

    delta_lat = latitude2 - latitude1
    delta_lon = longitude2 - longitude1

    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(latitude1)
        * math.cos(latitude2)
        * math.sin(delta_lon / 2) ** 2
    )
    distance_m = 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(haversine)))

    if distance_m <= 0.0:
        return 0.0, 0.0

    y = math.sin(delta_lon) * math.cos(latitude2)
    x = (
        math.cos(latitude1) * math.sin(latitude2)
        - math.sin(latitude1) * math.cos(latitude2) * math.cos(delta_lon)
    )
    course_deg = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
    return distance_m, course_deg


def resolve_start_datetime(start_datetime: datetime | None) -> datetime:
    if start_datetime is None:
        logging.info(
            "No --start-datetime provided; using %s so UTC time starts at 00:00:00.",
            DEFAULT_START_DATETIME.isoformat(),
        )
        return DEFAULT_START_DATETIME

    return start_datetime.astimezone(timezone.utc)


def point_datetime(start_datetime: datetime, relative_time_s: float) -> datetime:
    return start_datetime + timedelta(seconds=relative_time_s)


def format_nmea_time(value: datetime) -> str:
    rounded = value
    centiseconds = int(round(rounded.microsecond / 10_000.0))
    if centiseconds == 100:
        rounded = rounded + timedelta(seconds=1)
        centiseconds = 0
    return f"{rounded:%H%M%S}.{centiseconds:02d}"


def format_nmea_date(value: datetime) -> str:
    return value.strftime("%d%m%y")


def format_latitude(latitude_deg: float) -> tuple[str, str]:
    hemisphere = "N" if latitude_deg >= 0 else "S"
    absolute = abs(latitude_deg)
    degrees = int(absolute)
    minutes = (absolute - degrees) * 60.0
    return f"{degrees:02d}{minutes:07.4f}", hemisphere


def format_longitude(longitude_deg: float) -> tuple[str, str]:
    hemisphere = "E" if longitude_deg >= 0 else "W"
    absolute = abs(longitude_deg)
    degrees = int(absolute)
    minutes = (absolute - degrees) * 60.0
    return f"{degrees:03d}{minutes:07.4f}", hemisphere


def add_nmea_checksum(sentence_body: str) -> str:
    checksum = 0
    for character in sentence_body:
        checksum ^= ord(character)
    return f"${sentence_body}*{checksum:02X}"


def build_rmc(point: GeoPoint, speed_knots: float, course_deg: float, timestamp: datetime) -> str:
    latitude_field, latitude_hemisphere = format_latitude(point.latitude_deg)
    longitude_field, longitude_hemisphere = format_longitude(point.longitude_deg)
    sentence_body = ",".join(
        [
            "GPRMC",
            format_nmea_time(timestamp),
            "A",
            latitude_field,
            latitude_hemisphere,
            longitude_field,
            longitude_hemisphere,
            f"{speed_knots:.2f}",
            f"{course_deg:.2f}",
            format_nmea_date(timestamp),
            "",
            "",
        ]
    )
    return add_nmea_checksum(sentence_body)


def build_gga(point: GeoPoint, timestamp: datetime) -> str:
    latitude_field, latitude_hemisphere = format_latitude(point.latitude_deg)
    longitude_field, longitude_hemisphere = format_longitude(point.longitude_deg)
    sentence_body = ",".join(
        [
            "GPGGA",
            format_nmea_time(timestamp),
            latitude_field,
            latitude_hemisphere,
            longitude_field,
            longitude_hemisphere,
            "1",
            "08",
            "1.0",
            f"{point.altitude_m:.1f}",
            "M",
            "0.0",
            "M",
            "",
            "",
        ]
    )
    return add_nmea_checksum(sentence_body)


def write_nmea_file(
    output_path: Path,
    points: list[GeoPoint],
    start_datetime: datetime,
) -> int:
    motion = estimate_speed_and_course(points)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    line_count = 0
    with output_path.open("w", encoding="ascii", newline="") as handle:
        for point, (speed_knots, course_deg) in zip(points, motion):
            timestamp = point_datetime(start_datetime, point.relative_time_s)
            handle.write(build_rmc(point, speed_knots, course_deg, timestamp))
            handle.write("\r\n")
            handle.write(build_gga(point, timestamp))
            handle.write("\r\n")
            line_count += 2

    return line_count


def convert_file(
    input_path: Path,
    output_path: Path,
    start_datetime: datetime | None,
    time_start: float | None,
    time_end: float | None,
    sample_step: int,
) -> None:
    try:
        same_file = input_path.resolve() == output_path.resolve()
    except OSError:
        same_file = False

    if same_file:
        raise ConverterError("Input and output paths must be different.")

    raw_points = load_umt_points(input_path)
    logging.info("Input file: %s", input_path)
    logging.info("Total rows read: %d", len(raw_points))

    filtered_points = filter_points(raw_points, time_start, time_end)
    logging.info("Rows after filtering: %d", len(filtered_points))

    sampled_points = sample_points(filtered_points, sample_step)
    logging.info("Sample step: %d", sample_step)
    logging.info("Rows written: %d", len(sampled_points))

    coordinate_unit = detect_coordinate_unit(sampled_points)
    logging.info("Detected coordinate unit: %s", coordinate_unit)

    geo_points = convert_points(sampled_points, coordinate_unit)
    start_datetime_utc = resolve_start_datetime(start_datetime)
    logging.info("Using UTC start datetime: %s", start_datetime_utc.isoformat())

    sentence_count = write_nmea_file(output_path, geo_points, start_datetime_utc)
    logging.info("Number of generated NMEA sentences: %d", sentence_count)
    logging.info("Output file: %s", output_path)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    args = parse_args()

    try:
        convert_file(
            input_path=args.input,
            output_path=args.output,
            start_datetime=args.start_datetime,
            time_start=args.time_start,
            time_end=args.time_end,
            sample_step=args.sample_step,
        )
    except ConverterError as exc:
        logging.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        logging.error("Conversion cancelled.")
        return 130
    except Exception:
        logging.exception("Unexpected error during conversion.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
