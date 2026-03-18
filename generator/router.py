from __future__ import annotations

from abc import ABC, abstractmethod

from generator.models import RouteNode, RoutePath

COORDINATE_EPSILON = 1e-12


class RoutingProvider(ABC):
    @abstractmethod
    def plan_route(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        *,
        altitude_m: float = 0.0,
    ) -> RoutePath:
        """Build a route path between start and end coordinates."""


class MockRoutingProvider(RoutingProvider):
    def __init__(self, *, provider_name: str = "mock", bend_ratio: float = 0.5) -> None:
        if not 0.0 < bend_ratio < 1.0:
            raise ValueError("bend_ratio must be between 0 and 1.")
        self.provider_name = provider_name
        self.bend_ratio = bend_ratio

    def plan_route(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        *,
        altitude_m: float = 0.0,
    ) -> RoutePath:
        start = RouteNode(start_lat, start_lon, altitude_m=altitude_m, node_id="start")
        end = RouteNode(end_lat, end_lon, altitude_m=altitude_m, node_id="end")

        delta_lat = end_lat - start_lat
        delta_lon = end_lon - start_lon

        if (
            abs(delta_lat) <= COORDINATE_EPSILON
            or abs(delta_lon) <= COORDINATE_EPSILON
        ):
            nodes = [start, end]
        elif abs(delta_lat) >= abs(delta_lon):
            bend_lat = start_lat + (delta_lat * self.bend_ratio)
            nodes = [
                start,
                RouteNode(bend_lat, start_lon, altitude_m=altitude_m, node_id="turn_1"),
                RouteNode(bend_lat, end_lon, altitude_m=altitude_m, node_id="turn_2"),
                end,
            ]
        else:
            bend_lon = start_lon + (delta_lon * self.bend_ratio)
            nodes = [
                start,
                RouteNode(start_lat, bend_lon, altitude_m=altitude_m, node_id="turn_1"),
                RouteNode(end_lat, bend_lon, altitude_m=altitude_m, node_id="turn_2"),
                end,
            ]

        return RoutePath(nodes=_dedupe_adjacent_nodes(nodes), provider_name=self.provider_name)


def _dedupe_adjacent_nodes(nodes: list[RouteNode]) -> list[RouteNode]:
    if not nodes:
        return []

    deduped = [nodes[0]]
    for node in nodes[1:]:
        previous = deduped[-1]
        if (
            abs(node.lat - previous.lat) <= COORDINATE_EPSILON
            and abs(node.lon - previous.lon) <= COORDINATE_EPSILON
            and abs(node.altitude_m - previous.altitude_m) <= COORDINATE_EPSILON
        ):
            continue
        deduped.append(node)

    if len(deduped) == 1:
        only = deduped[0]
        deduped.append(
            RouteNode(
                only.lat,
                only.lon,
                altitude_m=only.altitude_m,
                node_id="end",
            )
        )

    return deduped
