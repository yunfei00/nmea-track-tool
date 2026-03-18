from __future__ import annotations

import unittest
from pathlib import Path
import sys

from core.track_model import TrackPoint

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from nmea_track.analysis.anomaly import AnomalyConfig, detect_anomalies


class AnomalyDetectionTests(unittest.TestCase):
    def test_detects_all_requested_anomaly_types(self) -> None:
        points = [
            TrackPoint(time_str="000000.00", lat=39.900000, lon=116.300000),
            TrackPoint(time_str="000001.00", lat=39.900001, lon=116.300001),
            TrackPoint(time_str="000010.00", lat=40.100000, lon=116.600000),
            TrackPoint(time_str="000009.00", lat=40.100100, lon=116.600100),
        ]
        config = AnomalyConfig(
            max_gap_seconds=5.0,
            max_jump_distance_m=50.0,
            max_speed_mps=20.0,
            max_speed_delta_mps=10.0,
        )

        anomalies = detect_anomalies(points, config=config)
        anomaly_types = {anomaly.type for anomaly in anomalies}

        self.assertIn("time_gap", anomaly_types)
        self.assertIn("time_non_increasing", anomaly_types)
        self.assertIn("jump", anomaly_types)
        self.assertIn("speed", anomaly_types)
        self.assertIn("speed_change", anomaly_types)


if __name__ == "__main__":
    unittest.main()
