from src.nmea_slimmer.checksum import compute_checksum, with_checksum
from src.nmea_slimmer.slim_engine import SlimOptions, slim_lines


def mk(body: str) -> str:
    return with_checksum(body)


def test_default_keep_and_drop():
    lines = [
        mk("GPGGA,000001,1,2,3"),
        mk("GPRMC,000001,A,1,2,3"),
        mk("GPGSA,A,3,1,2,3"),
        mk("GPGSV,2,1,8,01,1,1,1"),
        mk("GPVTG,1,2,3"),
        mk("GPGNS,1,2,3"),
        mk("GPDTM,1,2,3"),
        mk("GPXYZ,1,2,3"),
        "not nmea",
    ]
    out, stats = slim_lines(lines, SlimOptions())
    assert len(out) == 4
    assert stats.unknown_sentences == 1
    assert stats.non_nmea_lines == 1


def test_talker_convert_checksum():
    out, _ = slim_lines([mk("GNGGA,000001,1,2,3")], SlimOptions(convert_talker_to_gp=True))
    assert out[0].startswith("$GPGGA")
    body = out[0][1:].split("*")[0]
    cks = out[0].split("*")[1]
    assert compute_checksum(body) == cks


def test_gsv_rate_keep_complete_group():
    lines = [
        mk("GPGSV,2,1,8,01,1,1,1,02,2,2,2"),
        mk("GPGSV,2,2,8,03,3,3,3,04,4,4,4"),
        mk("GPGSV,2,1,8,01,1,1,1,02,2,2,2"),
        mk("GPGSV,2,2,8,03,3,3,3,04,4,4,4"),
    ]
    # with missing times, no drop
    out, _ = slim_lines(lines, SlimOptions(gsv_interval_sec=5))
    assert len(out) == 4
