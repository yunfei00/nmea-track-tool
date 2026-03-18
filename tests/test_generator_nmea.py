from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from core.nmea_parser import parse_nmea_lines
from generator.models import GeneratedTrackPoint
from generator.nmea_generator import generate_nmea_lines


class GeneratorNMEATests(unittest.TestCase):
    def test_generate_nmea_lines_from_generated_points(self) -> None:
        start_time = datetime(2026, 3, 12, tzinfo=timezone.utc)
        points = [
            GeneratedTrackPoint(
                seconds_from_start=0.0,
                timestamp=start_time,
                lat=48.1173,
                lon=11.5166667,
                speed_mps=10.0,
                course_deg=84.4,
                altitude_m=545.4,
            ),
            GeneratedTrackPoint(
                seconds_from_start=1.0,
                timestamp=start_time + timedelta(seconds=1),
                lat=48.1174,
                lon=11.5168,
                speed_mps=10.0,
                course_deg=84.4,
                altitude_m=545.5,
            ),
        ]

        lines = generate_nmea_lines(points)
        reparsed = parse_nmea_lines(lines)

        self.assertEqual(len(lines), 4)
        self.assertEqual(len(reparsed), 2)
        self.assertTrue(lines[0].startswith("$GPRMC,000000.00,A,"))
        self.assertTrue(lines[1].startswith("$GPGGA,000000.00,"))
        self.assertAlmostEqual(reparsed[0].lat, points[0].lat, places=4)
        self.assertAlmostEqual(reparsed[0].lon, points[0].lon, places=4)
        self.assertAlmostEqual(reparsed[0].alt_m, points[0].altitude_m, places=1)
        self.assertAlmostEqual(reparsed[0].course_deg, points[0].course_deg, places=2)
        self.assertAlmostEqual(reparsed[0].speed_knots, points[0].speed_knots, places=2)


if __name__ == "__main__":
    unittest.main()
