from __future__ import annotations

import unittest

from core.nmea_parser import parse_gpgga, parse_gprmc, parse_nmea_lines
from core.nmea_writer import trackpoint_to_nmea_sentences, write_nmea_lines
from core.track_model import TrackPoint


class NMEACoreTests(unittest.TestCase):
    def test_parser_merges_rmc_and_gga_into_track_point(self) -> None:
        lines = [
            "$GPRMC,000010.00,A,3954.3882,N,11622.0742,E,36.70,357.45,010170,,*0A",
            "$GPGGA,000010.00,3954.3882,N,11622.0742,E,1,08,1.0,54.0,M,0.0,M,,*68",
        ]

        points = parse_nmea_lines(lines)

        self.assertEqual(len(points), 1)
        point = points[0]
        self.assertEqual(point.time_str, "000010.00")
        self.assertAlmostEqual(point.lat, 39.90647, places=5)
        self.assertAlmostEqual(point.lon, 116.3679033333, places=5)
        self.assertEqual(point.alt_m, 54.0)
        self.assertEqual(point.speed_knots, 36.7)
        self.assertEqual(point.course_deg, 357.45)
        self.assertEqual(point.fix_quality, 1)
        self.assertEqual(point.num_sats, 8)
        self.assertEqual(point.hdop, 1.0)
        self.assertEqual(point.status, "A")

    def test_writer_generates_parseable_gprmc_and_gpgga(self) -> None:
        point = TrackPoint(
            time_str="123519.00",
            lat=48.1173,
            lon=11.5166667,
            alt_m=545.4,
            speed_knots=22.4,
            course_deg=84.4,
            fix_quality=1,
            num_sats=8,
            hdop=0.9,
            status="A",
        )

        rmc, gga = trackpoint_to_nmea_sentences(point, date_str="230394")
        merged = parse_nmea_lines([rmc, gga])

        self.assertTrue(rmc.startswith("$GPRMC,123519.00,A,"))
        self.assertTrue(gga.startswith("$GPGGA,123519.00,"))
        self.assertEqual(len(merged), 1)
        reparsed = merged[0]
        self.assertAlmostEqual(reparsed.lat, point.lat, places=4)
        self.assertAlmostEqual(reparsed.lon, point.lon, places=4)
        self.assertEqual(reparsed.alt_m, point.alt_m)
        self.assertEqual(reparsed.speed_knots, point.speed_knots)
        self.assertEqual(reparsed.course_deg, point.course_deg)
        self.assertEqual(reparsed.fix_quality, point.fix_quality)
        self.assertEqual(reparsed.num_sats, point.num_sats)
        self.assertEqual(reparsed.hdop, point.hdop)
        self.assertEqual(reparsed.status, point.status)

    def test_individual_sentence_parsers_work(self) -> None:
        rmc = parse_gprmc(
            "$GPRMC,000010.00,A,3954.3882,N,11622.0742,E,36.70,357.45,010170,,*0A"
        )
        gga = parse_gpgga(
            "$GPGGA,000010.00,3954.3882,N,11622.0742,E,1,08,1.0,54.0,M,0.0,M,,*68"
        )
        lines = write_nmea_lines([rmc, gga])

        self.assertEqual(rmc.status, "A")
        self.assertEqual(gga.fix_quality, 1)
        self.assertEqual(len(lines), 4)


if __name__ == "__main__":
    unittest.main()
