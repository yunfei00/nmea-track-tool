from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gui.generator_home import (
    DEFAULT_MAP_VIEW,
    MapViewport,
    ResolvedLocationInput,
    choose_startup_map_view,
    format_coordinate_pair,
    format_resolution_error,
    format_resolution_feedback,
    load_saved_map_view,
    load_startup_map_view,
    parse_coordinate_text,
    parse_coordinate_value,
    resolve_location_text,
    save_map_view,
    try_parse_coordinate_pair,
)


class GeneratorHomeHelperTests(unittest.TestCase):
    def test_load_startup_map_view_prefers_saved_view(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "map_home.json"
            saved_view = MapViewport(latitude=31.2304, longitude=121.4737, zoom=12)
            save_map_view(saved_view, path=state_path)

            loaded_view = load_startup_map_view(
                path=state_path,
                default_view=MapViewport(latitude=39.9042, longitude=116.4074, zoom=11),
            )

        self.assertEqual(loaded_view, saved_view)

    def test_load_saved_map_view_returns_none_for_invalid_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "map_home.json"
            state_path.write_text('{"lat":"bad","lon":121.4737,"zoom":12}', encoding="utf-8")

            loaded_view = load_saved_map_view(state_path)

        self.assertIsNone(loaded_view)

    def test_choose_startup_map_view_falls_back_to_default(self) -> None:
        default_view = MapViewport(latitude=22.5431, longitude=114.0579, zoom=10)

        selected_view = choose_startup_map_view(None, default_view=default_view)

        self.assertEqual(selected_view, default_view)
        self.assertNotEqual(selected_view, DEFAULT_MAP_VIEW)

    def test_try_parse_coordinate_pair_handles_valid_and_invalid_input(self) -> None:
        self.assertEqual(
            try_parse_coordinate_pair("39.9042", "116.4074"),
            (39.9042, 116.4074),
        )
        self.assertIsNone(try_parse_coordinate_pair("39.9042", ""))
        self.assertIsNone(try_parse_coordinate_pair("north", "116.4074"))

    def test_format_coordinate_pair_uses_fixed_six_decimal_precision(self) -> None:
        self.assertEqual(
            format_coordinate_pair(39.9042004, 116.4073996),
            ("39.904200", "116.407400"),
        )

    def test_parse_coordinate_value_validates_required_range(self) -> None:
        self.assertEqual(
            parse_coordinate_value("39.9042", "Latitude", -90.0, 90.0),
            39.9042,
        )
        with self.assertRaises(ValueError):
            parse_coordinate_value("200", "Longitude", -180.0, 180.0)

    def test_parse_coordinate_text_distinguishes_coordinates_from_address_text(self) -> None:
        self.assertEqual(
            parse_coordinate_text("39.9042, 116.4074"),
            (39.9042, 116.4074),
        )
        self.assertIsNone(parse_coordinate_text("Beijing South Railway Station"))
        self.assertIsNone(parse_coordinate_text("Beijing, China"))
        with self.assertRaises(ValueError):
            parse_coordinate_text("200, 116.4074")

    def test_resolve_location_text_uses_coordinates_directly(self) -> None:
        geocoder = _FakeGeocoder({"tiananmen": (39.9087, 116.3975)})

        resolved = resolve_location_text("39.9042,116.4074", geocoder)

        self.assertEqual(resolved.coordinates, (39.9042, 116.4074))
        self.assertEqual(resolved.source, "coordinates")
        self.assertEqual(geocoder.calls, [])

    def test_resolve_location_text_uses_geocoder_for_addresses(self) -> None:
        geocoder = _FakeGeocoder({"tiananmen": (39.9087, 116.3975)})

        resolved = resolve_location_text("Tiananmen", geocoder)

        self.assertEqual(resolved.coordinates, (39.9087, 116.3975))
        self.assertEqual(resolved.source, "address")
        self.assertEqual(geocoder.calls, ["Tiananmen"])

    def test_resolve_location_text_rejects_out_of_range_geocoder_values(self) -> None:
        geocoder = _FakeGeocoder({"\u897f\u5b89": (1004, 2336)})

        with self.assertRaises(ValueError):
            resolve_location_text("\u897f\u5b89", geocoder)

    def test_format_resolution_feedback_formats_address_result(self) -> None:
        message = format_resolution_feedback(
            ResolvedLocationInput(
                latitude=34.261004,
                longitude=108.9423363,
                source="address",
                query="\u897f\u5b89",
            )
        )

        self.assertEqual(message, "Resolved: \u897f\u5b89 -> (34.26, 108.94)")

    def test_format_resolution_error_formats_endpoint_context(self) -> None:
        self.assertEqual(
            format_resolution_error("start", "Latitude must be in [-90.0, 90.0]."),
            "Start input error: Latitude must be in [-90.0, 90.0].",
        )


class _FakeGeocoder:
    def __init__(self, results: dict[str, tuple[float, float]]) -> None:
        self._results = results
        self.calls: list[str] = []

    def geocode(self, query: str) -> tuple[float, float]:
        self.calls.append(query)
        return self._results[query.casefold()]


if __name__ == "__main__":
    unittest.main()
