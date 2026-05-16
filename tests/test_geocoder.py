from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch
from urllib.error import URLError

from geo.geocoder import GeocodingError, NominatimGeocoder


class GeocoderTests(unittest.TestCase):
    def test_nominatim_geocoder_parses_xian_result_as_valid_wgs84_coordinates(self) -> None:
        response_payload = _FakeHTTPResponse(
            json.dumps(
                [
                    {
                        "lat": "34.261004",
                        "lon": "108.9423363",
                        "display_name": "西安市, 陕西省, 中国",
                    }
                ]
            ).encode("utf-8")
        )
        geocoder = NominatimGeocoder()

        with self.assertLogs("geo.geocoder", level="DEBUG") as captured_logs:
            with patch("geo.geocoder.urlopen", return_value=response_payload):
                latitude, longitude = geocoder.geocode("西安")

        self.assertTrue(30.0 <= latitude <= 40.0)
        self.assertTrue(100.0 <= longitude <= 120.0)
        self.assertTrue(any("西安" in message for message in captured_logs.output))

    def test_nominatim_geocoder_returns_coordinates_and_uses_cache(self) -> None:
        response_payload = _FakeHTTPResponse(
            json.dumps([{"lat": "39.9042", "lon": "116.4074"}]).encode("utf-8")
        )
        geocoder = NominatimGeocoder(base_url="https://example.test", user_agent="test-agent")

        with patch("geo.geocoder.urlopen", return_value=response_payload) as urlopen_mock:
            first = geocoder.geocode("Tiananmen")
            second = geocoder.geocode("Tiananmen")

        self.assertEqual(first, (39.9042, 116.4074))
        self.assertEqual(second, (39.9042, 116.4074))
        self.assertEqual(urlopen_mock.call_count, 1)
        request = urlopen_mock.call_args.args[0]
        self.assertIn("format=jsonv2", request.full_url)
        self.assertIn("limit=1", request.full_url)

    def test_nominatim_geocoder_raises_for_empty_results(self) -> None:
        response_payload = _FakeHTTPResponse(json.dumps([]).encode("utf-8"))
        geocoder = NominatimGeocoder()

        with patch("geo.geocoder.urlopen", return_value=response_payload):
            with self.assertRaises(GeocodingError):
                geocoder.geocode("Unknown Place")

    def test_nominatim_geocoder_rejects_out_of_range_coordinates(self) -> None:
        response_payload = _FakeHTTPResponse(
            json.dumps([{"lat": "1004", "lon": "2336"}]).encode("utf-8")
        )
        geocoder = NominatimGeocoder()

        with self.assertLogs("geo.geocoder", level="WARNING") as captured_logs:
            with patch("geo.geocoder.urlopen", return_value=response_payload):
                with self.assertRaises(GeocodingError):
                    geocoder.geocode("西安")

        self.assertTrue(any("1004" in message for message in captured_logs.output))
        self.assertTrue(any("2336" in message for message in captured_logs.output))

    def test_nominatim_geocoder_raises_for_network_failure(self) -> None:
        geocoder = NominatimGeocoder()

        with patch("geo.geocoder.urlopen", side_effect=URLError("offline")):
            with self.assertRaises(GeocodingError):
                geocoder.geocode("Tiananmen")


class _FakeHTTPResponse(io.BytesIO):
    def __enter__(self) -> _FakeHTTPResponse:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


if __name__ == "__main__":
    unittest.main()
