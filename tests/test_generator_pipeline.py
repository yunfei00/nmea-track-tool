from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from core.nmea_parser import parse_nmea_file
from generator.kinematics import route_path_length_m
from generator.models import StopSegment
from generator.pipeline import generate_track, generate_track_to_nmea_file
from generator.router import MockRoutingProvider
from generator.traffic_lights import TrafficLightConfig


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

    def test_generate_track_pipeline_can_use_osrm_routing_mode(self) -> None:
        start_time = datetime(2026, 3, 12, tzinfo=timezone.utc)

        result = generate_track(
            39.9042,
            116.4074,
            39.9142,
            116.4274,
            routing_mode="osrm",
            osrm_geometry_format="geojson",
            osrm_requester=_fake_osrm_requester_geojson,
            sample_rate_hz=1.0,
            target_speed_mps=12.0,
            start_time=start_time,
            altitude_m=45.0,
        )

        self.assertEqual(result.route_path.provider_name, "osrm")
        self.assertEqual(len(result.route_path.nodes), 3)
        self.assertGreaterEqual(len(result.track_points), 2)
        self.assertEqual(len(result.nmea_lines), len(result.track_points) * 2)
        self.assertAlmostEqual(result.route_path.nodes[1].lat, 39.9092, places=6)
        self.assertAlmostEqual(result.route_path.nodes[1].lon, 116.4174, places=6)

    def test_generate_track_pipeline_supports_stop_segments(self) -> None:
        start_time = datetime(2026, 3, 12, tzinfo=timezone.utc)
        routing_provider = MockRoutingProvider()
        route_path = routing_provider.plan_route(
            39.9042,
            116.4074,
            39.9142,
            116.4274,
            altitude_m=45.0,
        )
        stop_distance_m = route_path_length_m(route_path) / 2.0

        result = generate_track(
            39.9042,
            116.4074,
            39.9142,
            116.4274,
            routing_provider=routing_provider,
            sample_rate_hz=1.0,
            target_speed_mps=12.0,
            stop_segments=[StopSegment(path_distance_m=stop_distance_m, duration_s=2.0)],
            start_time=start_time,
            altitude_m=45.0,
        )

        zero_speed_points = [
            point
            for point in result.track_points[1:-1]
            if point.speed_mps <= 1e-6
        ]
        self.assertGreaterEqual(len(zero_speed_points), 2)

    def test_generate_track_pipeline_can_insert_traffic_light_stops(self) -> None:
        start_time = datetime(2026, 3, 12, tzinfo=timezone.utc)

        result = generate_track(
            39.9042,
            116.4074,
            39.9142,
            116.4274,
            routing_provider=MockRoutingProvider(),
            sample_rate_hz=1.0,
            target_speed_mps=12.0,
            enable_traffic_lights=True,
            traffic_light_config=TrafficLightConfig(
                stop_probability=1.0,
                min_stop_duration_s=2.0,
                max_stop_duration_s=2.0,
                angle_threshold_deg=30.0,
            ),
            start_time=start_time,
            altitude_m=45.0,
        )

        middle_zero_speed_points = [
            point
            for point in result.track_points[1:-1]
            if point.speed_mps <= 1e-6
        ]
        stationary_headings = [point.course_deg for point in middle_zero_speed_points]

        self.assertGreaterEqual(len(result.traffic_light_stop_segments), 1)
        self.assertGreaterEqual(len(result.effective_stop_segments), 1)
        self.assertGreaterEqual(len(middle_zero_speed_points), 2)
        self.assertTrue(stationary_headings)
        self.assertTrue(all(0.0 <= heading <= 360.0 for heading in stationary_headings))


def _fake_osrm_requester_geojson(url: str, timeout_s: float) -> str:
    del url, timeout_s
    return """
    {
      "code": "Ok",
      "routes": [
        {
          "geometry": {
            "type": "LineString",
            "coordinates": [
              [116.4074, 39.9042],
              [116.4174, 39.9092],
              [116.4274, 39.9142]
            ]
          }
        }
      ]
    }
    """


if __name__ == "__main__":
    unittest.main()
