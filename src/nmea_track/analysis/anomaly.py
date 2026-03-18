from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from core.geo import haversine_m
from core.track_model import TrackPoint, time_str_to_seconds


@dataclass(slots=True)
class Anomaly:
    index: int
    type: str
    severity: str
    value: float
    message: str


@dataclass(slots=True)
class AnomalyConfig:
    max_gap_seconds: float = 10.0
    max_jump_distance_m: float = 100.0
    max_speed_mps: float = 80.0
    max_speed_delta_mps: float = 20.0


def detect_anomalies(
    points: Iterable[TrackPoint],
    config: AnomalyConfig | None = None,
) -> list[Anomaly]:
    cfg = config or AnomalyConfig()
    point_list = list(points)

    anomalies: list[Anomaly] = []
    previous_time: float | None = None
    previous_point: TrackPoint | None = None
    previous_speed_mps: float | None = None

    for index, point in enumerate(point_list):
        current_time = _safe_time_seconds(point.time_str)
        if current_time is None:
            continue

        if previous_time is not None:
            delta_seconds = current_time - previous_time
            if delta_seconds <= 0.0:
                anomalies.append(
                    Anomaly(
                        index=index,
                        type="time_non_increasing",
                        severity="error",
                        value=delta_seconds,
                        message=(
                            f"Time is non-increasing at index {index}: dt={delta_seconds:.3f}s"
                        ),
                    )
                )
            elif delta_seconds > cfg.max_gap_seconds:
                anomalies.append(
                    Anomaly(
                        index=index,
                        type="time_gap",
                        severity="warning",
                        value=delta_seconds,
                        message=(
                            f"Abnormal time gap at index {index}: dt={delta_seconds:.3f}s"
                        ),
                    )
                )

            if (
                previous_point is not None
                and point.lat is not None
                and point.lon is not None
                and previous_point.lat is not None
                and previous_point.lon is not None
            ):
                distance_m = haversine_m(
                    previous_point.lat,
                    previous_point.lon,
                    point.lat,
                    point.lon,
                )
                if distance_m > cfg.max_jump_distance_m:
                    anomalies.append(
                        Anomaly(
                            index=index,
                            type="jump",
                            severity="warning",
                            value=distance_m,
                            message=(
                                f"Position jump at index {index}: "
                                f"distance={distance_m:.3f}m"
                            ),
                        )
                    )

                if delta_seconds > 0.0:
                    speed_mps = distance_m / delta_seconds
                    if speed_mps > cfg.max_speed_mps:
                        anomalies.append(
                            Anomaly(
                                index=index,
                                type="speed",
                                severity="error",
                                value=speed_mps,
                                message=(
                                    f"Speed anomaly at index {index}: "
                                    f"speed={speed_mps:.3f}m/s"
                                ),
                            )
                        )

                    if previous_speed_mps is not None:
                        speed_delta_mps = abs(speed_mps - previous_speed_mps)
                        if speed_delta_mps > cfg.max_speed_delta_mps:
                            anomalies.append(
                                Anomaly(
                                    index=index,
                                    type="speed_change",
                                    severity="warning",
                                    value=speed_delta_mps,
                                    message=(
                                        f"Speed change anomaly at index {index}: "
                                        f"delta={speed_delta_mps:.3f}m/s"
                                    ),
                                )
                            )

                    previous_speed_mps = speed_mps

        previous_time = current_time
        previous_point = point

    return anomalies


def _safe_time_seconds(time_str: str) -> float | None:
    try:
        return time_str_to_seconds(time_str)
    except ValueError:
        return None
