from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from core.metrics import summarize_track
from core.nmea_parser import parse_nmea_file, parse_nmea_lines
from core.segment import split_track_segments
from core.track_model import TrackPoint, TrackSegment, TrackSummary
from core.validate import validate_track_points


@dataclass(slots=True)
class TrackResult:
    points: list[TrackPoint]
    segments: list[TrackSegment]
    summary: TrackSummary


def build_track_from_lines(
    lines: Iterable[str],
    *,
    max_speed_kmh: float = 300.0,
    split_gap_seconds: float = 10.0,
) -> TrackResult:
    parsed_points = parse_nmea_lines(lines)
    points = validate_track_points(parsed_points, max_speed_kmh=max_speed_kmh)
    segments = split_track_segments(points, split_gap_seconds=split_gap_seconds)
    summary = summarize_track(points, segments)
    return TrackResult(points=points, segments=segments, summary=summary)


def build_track_from_file(
    path: str | Path,
    *,
    max_speed_kmh: float = 300.0,
    split_gap_seconds: float = 10.0,
) -> TrackResult:
    parsed_points = parse_nmea_file(path)
    points = validate_track_points(parsed_points, max_speed_kmh=max_speed_kmh)
    segments = split_track_segments(points, split_gap_seconds=split_gap_seconds)
    summary = summarize_track(points, segments)
    return TrackResult(points=points, segments=segments, summary=summary)
