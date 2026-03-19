from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from generator.pipeline import GenerationResult, generate_track_to_nmea_file
from generator.traffic_lights import TrafficLightConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a replayable NMEA route from start/end coordinates.",
    )
    parser.add_argument(
        "--start",
        required=True,
        type=parse_coordinate_pair,
        metavar="LAT,LON",
        help='Start coordinate pair, for example "39.9042,116.4074".',
    )
    parser.add_argument(
        "--end",
        required=True,
        type=parse_coordinate_pair,
        metavar="LAT,LON",
        help='End coordinate pair, for example "39.9142,116.4274".',
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output NMEA file path.",
    )
    parser.add_argument(
        "--routing-mode",
        choices=["osrm", "mock"],
        default="osrm",
        help="Routing backend to use. Default: osrm",
    )
    parser.add_argument(
        "--osrm-base-url",
        default="https://router.project-osrm.org",
        help="Base URL for the OSRM routing service.",
    )
    parser.add_argument(
        "--target-speed-kmh",
        type=float,
        default=50.0,
        help="Target cruising speed in km/h. Default: 50.0",
    )
    parser.add_argument(
        "--start-datetime",
        type=parse_start_datetime,
        help="UTC start datetime in ISO 8601 format, for example 2026-03-12T00:00:00Z.",
    )
    parser.add_argument(
        "--disable-traffic-lights",
        action="store_true",
        help="Disable traffic-light stop simulation.",
    )
    parser.add_argument(
        "--traffic-light-stop-probability",
        type=float,
        default=0.3,
        help="Probability of stopping at a detected candidate intersection. Default: 0.3",
    )
    parser.add_argument(
        "--traffic-light-min-stop-duration",
        type=float,
        default=2.0,
        help="Minimum traffic-light stop duration in seconds. Default: 2.0",
    )
    parser.add_argument(
        "--traffic-light-max-stop-duration",
        type=float,
        default=10.0,
        help="Maximum traffic-light stop duration in seconds. Default: 10.0",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = generate_track_file(
            start=args.start,
            end=args.end,
            output_path=args.output,
            routing_mode=args.routing_mode,
            osrm_base_url=args.osrm_base_url,
            target_speed_kmh=args.target_speed_kmh,
            start_datetime=args.start_datetime,
            enable_traffic_lights=not args.disable_traffic_lights,
            traffic_light_stop_probability=args.traffic_light_stop_probability,
            traffic_light_min_stop_duration_s=args.traffic_light_min_stop_duration,
            traffic_light_max_stop_duration_s=args.traffic_light_max_stop_duration,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(format_generation_result(result, args.output))
    return 0


def generate_track_file(
    *,
    start: tuple[float, float],
    end: tuple[float, float],
    output_path: str | Path,
    routing_mode: str = "osrm",
    osrm_base_url: str = "https://router.project-osrm.org",
    target_speed_kmh: float = 50.0,
    start_datetime: datetime | None = None,
    enable_traffic_lights: bool = True,
    traffic_light_stop_probability: float = 0.3,
    traffic_light_min_stop_duration_s: float = 2.0,
    traffic_light_max_stop_duration_s: float = 10.0,
) -> GenerationResult:
    if target_speed_kmh <= 0.0:
        raise ValueError("--target-speed-kmh must be greater than zero.")

    traffic_light_config = TrafficLightConfig(
        stop_probability=traffic_light_stop_probability,
        min_stop_duration_s=traffic_light_min_stop_duration_s,
        max_stop_duration_s=traffic_light_max_stop_duration_s,
    )
    start_lat, start_lon = start
    end_lat, end_lon = end

    return generate_track_to_nmea_file(
        start_lat,
        start_lon,
        end_lat,
        end_lon,
        output_path,
        routing_mode=routing_mode,
        osrm_base_url=osrm_base_url,
        target_speed_mps=target_speed_kmh / 3.6,
        enable_traffic_lights=enable_traffic_lights,
        traffic_light_config=traffic_light_config,
        start_time=start_datetime,
    )


def format_generation_result(result: GenerationResult, output_path: str | Path) -> str:
    lines = [
        "Generated NMEA Track",
        f"Route provider: {result.route_path.provider_name}",
        f"Route nodes: {len(result.route_path.nodes)}",
        f"Track points: {len(result.track_points)}",
        f"Route distance (meters): {result.route_distance_m:.2f}",
        f"Traffic-light stops: {len(result.traffic_light_stop_segments)}",
        f"Output file: {Path(output_path)}",
    ]
    return "\n".join(lines)


def parse_coordinate_pair(value: str) -> tuple[float, float]:
    latitude_text, separator, longitude_text = value.strip().partition(",")
    if not separator:
        raise argparse.ArgumentTypeError(
            'Coordinate must be in "lat,lon" form, for example "39.9042,116.4074".'
        )

    try:
        latitude = float(latitude_text.strip())
        longitude = float(longitude_text.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            'Coordinate must be numeric, for example "39.9042,116.4074".'
        ) from exc

    if not -90.0 <= latitude <= 90.0:
        raise argparse.ArgumentTypeError(f"Latitude must be in [-90, 90], got {latitude}.")
    if not -180.0 <= longitude <= 180.0:
        raise argparse.ArgumentTypeError(f"Longitude must be in [-180, 180], got {longitude}.")

    return latitude, longitude


def parse_start_datetime(value: str) -> datetime:
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Invalid --start-datetime. Use ISO 8601, for example 2026-03-12T00:00:00Z."
        ) from exc

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


if __name__ == "__main__":
    sys.exit(main())
