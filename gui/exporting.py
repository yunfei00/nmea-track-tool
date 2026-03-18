from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from core.nmea_writer import write_nmea_file
from core.pipeline import TrackResult

POINT_CSV_FIELDNAMES = [
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
    "anomaly_flags",
    "calculated_speed_kmh",
]


def export_cleaned_nmea(result: TrackResult, path: str | Path) -> int:
    _ensure_exportable_nmea_points(result)
    return write_nmea_file(result.points, path)


def export_points_csv(result: TrackResult, path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=POINT_CSV_FIELDNAMES)
        writer.writeheader()
        for point in result.points:
            row = asdict(point)
            row["anomaly_flags"] = "; ".join(point.anomaly_flags)
            writer.writerow(row)


def export_summary_json(result: TrackResult, path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        json.dump(asdict(result.summary), handle, indent=2)
        handle.write("\n")


def _ensure_exportable_nmea_points(result: TrackResult) -> None:
    invalid_indexes: list[int] = []
    for index, point in enumerate(result.points):
        if point.lat is None or point.lon is None:
            invalid_indexes.append(index)
            continue
        if not -90.0 <= point.lat <= 90.0:
            invalid_indexes.append(index)
            continue
        if not -180.0 <= point.lon <= 180.0:
            invalid_indexes.append(index)

    if invalid_indexes:
        preview = ", ".join(str(index) for index in invalid_indexes[:5])
        if len(invalid_indexes) > 5:
            preview = f"{preview}, ..."
        raise ValueError(
            "Cannot export cleaned NMEA because some current points do not have "
            f"writable coordinates. Row indexes: {preview}"
        )
