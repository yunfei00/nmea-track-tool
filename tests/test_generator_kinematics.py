from __future__ import annotations

import unittest
from datetime import datetime, timezone

from generator.kinematics import interpolate_route_path, route_path_length_m
from generator.models import RouteNode, RoutePath, StopSegment


class GeneratorKinematicsTests(unittest.TestCase):
    def test_interpolate_route_path_reaches_endpoint_with_monotonic_timestamps(self) -> None:
        start_time = datetime(2026, 3, 12, tzinfo=timezone.utc)
        route_path = RoutePath(
            nodes=[
                RouteNode(0.0, 0.0, node_id="start"),
                RouteNode(0.0, 0.001, node_id="end"),
            ],
            provider_name="test",
        )

        points = interpolate_route_path(
            route_path,
            sample_rate_hz=1.0,
            target_speed_mps=15.0,
            start_time=start_time,
        )

        self.assertAlmostEqual(points[0].seconds_from_start, 0.0, places=6)
        self.assertEqual(points[0].timestamp, start_time)
        self.assertAlmostEqual(points[0].lon, 0.0, places=7)
        self.assertAlmostEqual(points[-1].lon, 0.001, places=7)
        self.assertAlmostEqual(points[-1].speed_mps, 0.0, places=6)
        self.assertTrue(
            all(
                first.seconds_from_start < second.seconds_from_start
                for first, second in zip(points, points[1:])
            )
        )

    def test_interpolate_route_path_uses_accel_cruise_decel_speed_profile(self) -> None:
        route_path = RoutePath(
            nodes=[
                RouteNode(0.0, 0.0, node_id="start"),
                RouteNode(0.0, 0.01, node_id="end"),
            ],
            provider_name="test",
        )

        points = interpolate_route_path(
            route_path,
            sample_rate_hz=1.0,
            target_speed_mps=20.0,
            acceleration_mps2=2.0,
            deceleration_mps2=2.0,
        )

        speeds = [point.speed_mps for point in points]
        peak_index = speeds.index(max(speeds))

        self.assertAlmostEqual(speeds[0], 0.0, places=6)
        self.assertAlmostEqual(speeds[-1], 0.0, places=6)
        self.assertAlmostEqual(max(speeds), 20.0, delta=0.5)
        self.assertGreater(peak_index, 0)
        self.assertLess(peak_index, len(speeds) - 1)
        self.assertTrue(
            all(
                speeds[index] <= speeds[index + 1] + 1e-6
                for index in range(peak_index)
            )
        )
        self.assertTrue(
            all(
                speeds[index] >= speeds[index + 1] - 1e-6
                for index in range(peak_index, len(speeds) - 1)
            )
        )
        self.assertTrue(
            all(
                abs(second - first) <= 2.0 + 1e-6
                for first, second in zip(speeds, speeds[1:])
            )
        )

    def test_interpolate_route_path_supports_stop_segments(self) -> None:
        route_path = RoutePath(
            nodes=[
                RouteNode(0.0, 0.0, node_id="start"),
                RouteNode(0.0, 0.01, node_id="end"),
            ],
            provider_name="test",
        )
        stop_distance_m = route_path_length_m(route_path) / 2.0

        points = interpolate_route_path(
            route_path,
            sample_rate_hz=1.0,
            target_speed_mps=15.0,
            stop_segments=[StopSegment(path_distance_m=stop_distance_m, duration_s=3.0)],
        )

        longest_stationary_run = _longest_stationary_run(points)

        self.assertGreaterEqual(len(longest_stationary_run), 4)
        self.assertTrue(all(points[index].speed_mps <= 1e-6 for index in longest_stationary_run))
        run_duration_s = (
            points[longest_stationary_run[-1]].seconds_from_start
            - points[longest_stationary_run[0]].seconds_from_start
        )
        self.assertGreaterEqual(run_duration_s, 3.0)
        self.assertGreater(points[longest_stationary_run[-1] + 1].speed_mps, 0.0)

    def test_interpolate_route_path_keeps_heading_continuous_through_stop(self) -> None:
        route_path = RoutePath(
            nodes=[
                RouteNode(0.0, 0.0, node_id="start"),
                RouteNode(0.0, 0.01, node_id="end"),
            ],
            provider_name="test",
        )
        stop_distance_m = route_path_length_m(route_path) / 2.0

        points = interpolate_route_path(
            route_path,
            sample_rate_hz=1.0,
            target_speed_mps=15.0,
            stop_segments=[StopSegment(path_distance_m=stop_distance_m, duration_s=3.0)],
        )

        longest_stationary_run = _longest_stationary_run(points)
        stationary_headings = [points[index].course_deg for index in longest_stationary_run]

        self.assertTrue(stationary_headings)
        self.assertTrue(all(abs(heading - 90.0) <= 0.5 for heading in stationary_headings))
        self.assertAlmostEqual(points[-1].course_deg, 90.0, delta=0.5)


def _longest_stationary_run(points: list[object]) -> list[int]:
    longest_run: list[int] = []
    current_run = [0]

    for index in range(1, len(points)):
        previous = points[index - 1]
        current = points[index]
        if abs(previous.lat - current.lat) <= 1e-12 and abs(previous.lon - current.lon) <= 1e-12:
            current_run.append(index)
            if len(current_run) > len(longest_run):
                longest_run = list(current_run)
            continue

        current_run = [index]

    return longest_run


if __name__ == "__main__":
    unittest.main()
