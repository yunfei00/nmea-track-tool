from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from core.nmea_parser import parse_nmea_file
from generator.pipeline import generate_track, generate_track_to_nmea_file
from generator.router import MockRoutingProvider


class GeneratorPipelineTests(unittest.TestCase):
    def test_generate_track_pipeline_with_mock_router(self) -> None:
        start_time = datetime(2026, 3, 12, tzinfo=timezone.utc)

        result = generate_track(
            39.9042,
            116.4074,
            39.9142,
            116.4274,
            routing_provider=MockRoutingProvider(),
            sample_rate_hz=1.0,
            target_speed_mps=12.0,
            start_time=start_time,
            altitude_m=45.0,
        )

        self.assertEqual(result.route_path.provider_name, "mock")
        self.assertGreaterEqual(len(result.route_path.nodes), 2)
        self.assertGreaterEqual(len(result.track_points), 2)
        self.assertEqual(len(result.nmea_lines), len(result.track_points) * 2)
        self.assertAlmostEqual(result.track_points[0].lat, 39.9042, places=6)
        self.assertAlmostEqual(result.track_points[0].lon, 116.4074, places=6)
        self.assertAlmostEqual(result.track_points[-1].lat, 39.9142, places=6)
        self.assertAlmostEqual(result.track_points[-1].lon, 116.4274, places=6)
        self.assertGreater(result.route_distance_m, 0.0)

    def test_generate_track_pipeline_can_export_parseable_nmea_file(self) -> None:
        start_time = datetime(2026, 3, 12, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "generated_track.nmea"
            result = generate_track_to_nmea_file(
                39.9042,
                116.4074,
                39.9142,
                116.4274,
                output_path,
                routing_provider=MockRoutingProvider(),
                sample_rate_hz=1.0,
                target_speed_mps=12.0,
                start_time=start_time,
                altitude_m=45.0,
            )

            reparsed = parse_nmea_file(output_path)

        self.assertTrue(output_path.name.endswith(".nmea"))
        self.assertEqual(len(reparsed), len(result.track_points))
        self.assertAlmostEqual(reparsed[0].lat, result.track_points[0].lat, places=4)
        self.assertAlmostEqual(reparsed[-1].lon, result.track_points[-1].lon, places=4)


if __name__ == "__main__":
    unittest.main()
