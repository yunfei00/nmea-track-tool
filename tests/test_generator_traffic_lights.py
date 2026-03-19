from __future__ import annotations

import unittest

from generator.models import RouteNode, RoutePath
from generator.traffic_lights import (
    TrafficLightConfig,
    detect_candidate_stop_points,
    simulate_traffic_light_stop_segments,
)


class GeneratorTrafficLightTests(unittest.TestCase):
    def test_detect_candidate_stop_points_finds_sharp_turn(self) -> None:
        route_path = RoutePath(
            nodes=[
                RouteNode(0.0, 0.0, node_id="start"),
                RouteNode(0.0, 0.001, node_id="turn"),
                RouteNode(0.001, 0.001, node_id="end"),
            ],
            provider_name="test",
        )

        candidates = detect_candidate_stop_points(route_path, angle_threshold_deg=30.0)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].node_index, 1)
        self.assertAlmostEqual(candidates[0].lat, 0.0, places=7)
        self.assertAlmostEqual(candidates[0].lon, 0.001, places=7)
        self.assertAlmostEqual(candidates[0].turn_angle_deg, 90.0, delta=0.5)

    def test_simulate_traffic_light_stop_segments_respects_probability(self) -> None:
        route_path = RoutePath(
            nodes=[
                RouteNode(0.0, 0.0, node_id="start"),
                RouteNode(0.0, 0.001, node_id="turn"),
                RouteNode(0.001, 0.001, node_id="end"),
            ],
            provider_name="test",
        )

        no_stop_segments = simulate_traffic_light_stop_segments(
            route_path,
            config=TrafficLightConfig(
                stop_probability=0.0,
                min_stop_duration_s=3.0,
                max_stop_duration_s=3.0,
            ),
        )
        always_stop_segments = simulate_traffic_light_stop_segments(
            route_path,
            config=TrafficLightConfig(
                stop_probability=1.0,
                min_stop_duration_s=4.0,
                max_stop_duration_s=4.0,
            ),
        )

        self.assertEqual(no_stop_segments, [])
        self.assertEqual(len(always_stop_segments), 1)
        self.assertAlmostEqual(always_stop_segments[0].duration_s, 4.0, places=6)
        self.assertGreater(always_stop_segments[0].path_distance_m, 0.0)


if __name__ == "__main__":
    unittest.main()
