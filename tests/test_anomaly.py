from __future__ import annotations

import unittest

from core.anomaly import detect_anomalies
from core.track_model import TrackPoint


class AnomalyDetectionTests(unittest.TestCase):
    def test_detect_anomalies_flags_high_speed_points(self) -> None:
        points = [
            TrackPoint(time_str="000000.00", lat=0.0, lon=0.0),
            TrackPoint(time_str="000001.00", lat=0.0, lon=0.001),
        ]

        detected = detect_anomalies(points)

        self.assertEqual(detected[0].anomaly_flags, [])
        self.assertIn("high_speed", detected[1].anomaly_flags)
        self.assertNotIn("jump", detected[1].anomaly_flags)

    def test_detect_anomalies_flags_jump_points(self) -> None:
        points = [
            TrackPoint(time_str="000000.00", lat=0.0, lon=0.0),
            TrackPoint(time_str="000001.00", lat=0.0, lon=0.002),
        ]

        detected = detect_anomalies(points)

        self.assertIn("jump", detected[1].anomaly_flags)
        self.assertIn("high_speed", detected[1].anomaly_flags)

    def test_detect_anomalies_flags_time_errors(self) -> None:
        points = [
            TrackPoint(time_str="000002.00", lat=0.0, lon=0.0),
            TrackPoint(time_str="000001.00", lat=0.0, lon=0.001),
        ]

        detected = detect_anomalies(points)

        self.assertEqual(detected[0].anomaly_flags, [])
        self.assertEqual(detected[1].anomaly_flags, ["time_error"])


if __name__ == "__main__":
    unittest.main()
