from __future__ import annotations

import unittest
from urllib import error

from generator.router import OSRMRoutingProvider, RoutingError, route_path_from_osrm_response


class GeneratorRouterTests(unittest.TestCase):
    def test_route_path_from_osrm_response_parses_geojson_geometry(self) -> None:
        route_path = route_path_from_osrm_response(
            {
                "code": "Ok",
                "routes": [
                    {
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [
                                [116.4074, 39.9042],
                                [116.4174, 39.9092],
                                [116.4274, 39.9142],
                            ],
                        }
                    }
                ],
            },
            altitude_m=50.0,
            geometry_format="geojson",
        )

        self.assertEqual(route_path.provider_name, "osrm")
        self.assertEqual(len(route_path.nodes), 3)
        self.assertAlmostEqual(route_path.nodes[0].lat, 39.9042, places=6)
        self.assertAlmostEqual(route_path.nodes[0].lon, 116.4074, places=6)
        self.assertAlmostEqual(route_path.nodes[1].altitude_m, 50.0, places=6)

    def test_route_path_from_osrm_response_parses_polyline_geometry(self) -> None:
        route_path = route_path_from_osrm_response(
            {
                "code": "Ok",
                "routes": [
                    {
                        "geometry": "_p~iF~ps|U_ulLnnqC_mqNvxq`@",
                    }
                ],
            },
            geometry_format="polyline",
        )

        self.assertEqual(len(route_path.nodes), 3)
        self.assertAlmostEqual(route_path.nodes[0].lat, 38.5, places=5)
        self.assertAlmostEqual(route_path.nodes[0].lon, -120.2, places=5)
        self.assertAlmostEqual(route_path.nodes[1].lat, 40.7, places=5)
        self.assertAlmostEqual(route_path.nodes[1].lon, -120.95, places=5)
        self.assertAlmostEqual(route_path.nodes[2].lat, 43.252, places=5)
        self.assertAlmostEqual(route_path.nodes[2].lon, -126.453, places=5)

    def test_osrm_provider_raises_on_network_error(self) -> None:
        provider = OSRMRoutingProvider(
            requester=_raising_requester,
        )

        with self.assertRaises(RoutingError) as context:
            provider.plan_route(39.9042, 116.4074, 39.9142, 116.4274)

        self.assertIn("OSRM request failed", str(context.exception))

    def test_osrm_provider_raises_on_empty_routes(self) -> None:
        provider = OSRMRoutingProvider(
            requester=_empty_routes_requester,
        )

        with self.assertRaises(RoutingError) as context:
            provider.plan_route(39.9042, 116.4074, 39.9142, 116.4274)

        self.assertIn("no routes", str(context.exception).lower())


def _raising_requester(url: str, timeout_s: float) -> str:
    del url, timeout_s
    raise error.URLError("offline")


def _empty_routes_requester(url: str, timeout_s: float) -> str:
    del url, timeout_s
    return '{"code":"Ok","routes":[]}'


if __name__ == "__main__":
    unittest.main()
