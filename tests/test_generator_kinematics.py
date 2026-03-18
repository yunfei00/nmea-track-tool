from __future__ import annotations

import unittest
from datetime import datetime, timezone

from generator.kinematics import interpolate_route_path, route_path_length_m
from generator.models import RouteNode, RoutePath


class GeneratorKinematicsTests(unittest.TestCase):
    def test_interpolate_route_path_keeps_fixed_rate_and_hits_endpoint(self) -> None:
        start_time = datetime(2026, 3, 12, tzinfo=timezone.utc)
        route_path = RoutePath(
            nodes=[
                RouteNode(0.0, 0.0, node_id="start"),
                RouteNode(0.0, 0.001, node_id="end"),
            ],
            provider_name="test",
        )
        target_speed_mps = route_path_length_m(route_path) / 2.0

        points = interpolate_route_path(
            route_path,
            sample_rate_hz=1.0,
            target_speed_mps=target_speed_mps,
            start_time=start_time,
        )

        self.assertEqual(len(points), 3)
        self.assertAlmostEqual(points[0].seconds_from_start, 0.0, places=6)
        self.assertAlmostEqual(points[1].seconds_from_start, 1.0, places=6)
        self.assertAlmostEqual(points[2].seconds_from_start, 2.0, places=6)
        self.assertEqual(points[0].timestamp, start_time)
        self.assertEqual(points[1].timestamp, start_time.replace(second=1))
        self.assertAlmostEqual(points[0].lon, 0.0, places=7)
        self.assertAlmostEqual(points[1].lon, 0.0005, places=6)
        self.assertAlmostEqual(points[2].lon, 0.001, places=7)

    def test_interpolate_route_path_updates_heading_on_turn(self) -> None:
        route_path = RoutePath(
            nodes=[
                RouteNode(0.0, 0.0, node_id="start"),
                RouteNode(0.0, 0.001, node_id="turn"),
                RouteNode(0.001, 0.001, node_id="end"),
            ],
            provider_name="test",
        )
        target_speed_mps = route_path_length_m(route_path) / 2.0

        points = interpolate_route_path(
            route_path,
            sample_rate_hz=1.0,
            target_speed_mps=target_speed_mps,
        )

        self.assertEqual(len(points), 3)
        self.assertAlmostEqual(points[0].course_deg, 90.0, delta=0.5)
        self.assertAlmostEqual(points[1].course_deg, 0.0, delta=0.5)
        self.assertAlmostEqual(points[2].course_deg, 0.0, delta=0.5)


if __name__ == "__main__":
    unittest.main()
