from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from core.pipeline import TrackResult, build_track_from_file

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if SRC_DIR.is_dir() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from nmea_track.analysis import Anomaly, detect_anomalies


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NMEA track analysis CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze an NMEA file and print a readable summary.",
    )
    analyze_parser.add_argument("input_file", type=Path, help="Path to the input NMEA file")
    analyze_parser.add_argument(
        "--export-points-csv",
        type=Path,
        help="Optional path to export TrackPoint rows as CSV.",
    )
    analyze_parser.add_argument(
        "--export-summary-json",
        type=Path,
        help="Optional path to export TrackSummary as JSON.",
    )
    analyze_parser.add_argument(
        "--detect-anomalies",
        action="store_true",
        help="Detect time, jump, and speed anomalies from parsed points.",
    )
    analyze_parser.set_defaults(handler=handle_analyze)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return args.handler(args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def handle_analyze(args: argparse.Namespace) -> int:
    result = build_track_from_file(args.input_file)
    print(format_track_result(result))
    if args.detect_anomalies:
        anomalies = detect_anomalies(result.points)
        print()
        print(format_anomaly_summary(anomalies))

    if args.export_points_csv:
        write_points_csv(result, args.export_points_csv)
        print(f"Points CSV exported: {args.export_points_csv}")

    if args.export_summary_json:
        write_summary_json(result, args.export_summary_json)
        print(f"Summary JSON exported: {args.export_summary_json}")

    return 0


def format_track_result(result: TrackResult) -> str:
    summary = result.summary
    lines = [
        "NMEA Track Summary",
        f"Total points: {summary.total_points}",
        f"Valid points: {summary.valid_points}",
        f"Invalid points: {summary.invalid_points}",
        f"Segment count: {summary.segment_count}",
        f"Total distance (meters): {summary.total_distance_m:.2f}",
        f"Duration (seconds): {summary.duration_seconds:.2f}",
        f"Average speed (km/h): {summary.avg_speed_kmh:.2f}",
        f"Max speed (km/h): {summary.max_speed_kmh:.2f}",
    ]
    return "\n".join(lines)


def write_points_csv(result: TrackResult, path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(result.points[0]).keys()) if result.points else [
        "time_str",
        "lat",
        "lon",
        "alt_m",
        "speed_knots",
        "course_deg",
        "fix_quality",
        "num_sats",
        "hdop",
        "status",
        "is_valid",
        "invalid_reason",
        "calculated_speed_kmh",
    ]

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for point in result.points:
            writer.writerow(asdict(point))


def write_summary_json(result: TrackResult, path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        json.dump(asdict(result.summary), handle, indent=2)
        handle.write("\n")


def format_anomaly_summary(anomalies: Sequence[Anomaly]) -> str:
    totals = {
        "speed": 0,
        "jump": 0,
        "time": 0,
    }
    for anomaly in anomalies:
        anomaly_type = getattr(anomaly, "type", "")
        if anomaly_type.startswith("speed"):
            totals["speed"] += 1
        elif anomaly_type.startswith("time"):
            totals["time"] += 1
        elif anomaly_type == "jump":
            totals["jump"] += 1

    lines = [
        "Anomaly summary:",
        f"- total: {len(anomalies)}",
        f"- speed: {totals['speed']}",
        f"- jump: {totals['jump']}",
        f"- time: {totals['time']}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
