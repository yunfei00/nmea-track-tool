from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Final
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_NOMINATIM_BASE_URL: Final[str] = "https://nominatim.openstreetmap.org"
DEFAULT_NOMINATIM_USER_AGENT: Final[str] = "nmea-track-tool/1.0"
logger = logging.getLogger(__name__)


class GeocodingError(RuntimeError):
    pass


@dataclass
class NominatimGeocoder:
    base_url: str = DEFAULT_NOMINATIM_BASE_URL
    user_agent: str = DEFAULT_NOMINATIM_USER_AGENT
    timeout_s: float = 10.0
    _cache: dict[str, tuple[float, float]] = field(default_factory=dict)

    def geocode(self, query: str) -> tuple[float, float]:
        query_text = " ".join(query.strip().split())
        normalized_query = _normalize_query(query_text)
        if not normalized_query:
            raise GeocodingError("Address is required.")

        cached_coordinates = self._cache.get(normalized_query)
        if cached_coordinates is not None:
            return cached_coordinates

        request = Request(
            self._build_search_url(query_text),
            headers={
                "Accept": "application/json",
                "User-Agent": self.user_agent,
            },
        )

        try:
            with urlopen(request, timeout=self.timeout_s) as response:
                payload = json.load(response)
        except URLError as exc:
            raise GeocodingError(
                f'Geocoding service is unavailable for "{query}". Please try again.'
            ) from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise GeocodingError(
                f'Could not decode geocoding results for "{query}".'
            ) from exc

        logger.debug(
            'Geocoder raw response for "%s": %s',
            query,
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        )

        if not isinstance(payload, list) or not payload:
            raise GeocodingError(f'No location results found for "{query}".')

        first_result = payload[0]
        try:
            latitude = _parse_wgs84_coordinate(
                first_result,
                field_name="lat",
                minimum=-90.0,
                maximum=90.0,
                query=query,
            )
            longitude = _parse_wgs84_coordinate(
                first_result,
                field_name="lon",
                minimum=-180.0,
                maximum=180.0,
                query=query,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise GeocodingError(
                f'Geocoding response did not include coordinates for "{query}".'
            ) from exc

        coordinates = (latitude, longitude)
        self._cache[normalized_query] = coordinates
        return coordinates

    def _build_search_url(self, query: str) -> str:
        query_params = urlencode(
            {
                "q": query,
                "format": "jsonv2",
                "limit": 1,
            }
        )
        return f"{self.base_url.rstrip('/')}/search?{query_params}"


def _normalize_query(query: str) -> str:
    return " ".join(query.strip().split()).casefold()


def _parse_wgs84_coordinate(
    response_payload: dict[str, object],
    *,
    field_name: str,
    minimum: float,
    maximum: float,
    query: str,
) -> float:
    try:
        value = float(response_payload[field_name])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(field_name) from exc

    if not minimum <= value <= maximum:
        logger.warning(
            'Rejecting geocoder response for "%s": %s',
            query,
            json.dumps(response_payload, ensure_ascii=False, separators=(",", ":")),
        )
        raise GeocodingError(
            f'Geocoding returned invalid {field_name} for "{query}".'
        )

    return value
