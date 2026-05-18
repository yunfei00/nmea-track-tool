from src.nmea_slimmer.checksum import compute_checksum, with_checksum
from src.nmea_slimmer.slim_engine import SlimOptions, extract_nmea_sentences, slim_lines


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


def test_extract_normal_line_by_line():
    text = mk("GPRMC,000001,A,1,2,3") + "\n" + mk("GPGGA,000001,1,2,3") + "\n"
    lines = extract_nmea_sentences(text)
    assert len(lines) == 2


def test_extract_two_concatenated_sentences():
    text = mk("GPRMC,000001,A,1,2,3") + mk("GPGGA,000001,1,2,3")
    lines = extract_nmea_sentences(text)
    assert len(lines) == 2


def test_extract_multiple_concatenated_sentences():
    text = "".join(
        [
            mk("GPRMC,000001,A,1,2,3"),
            mk("GPGGA,000001,1,2,3"),
            mk("GPGSA,A,3,1,2,3"),
            mk("GPGSV,2,1,8,01,1,1,1"),
        ]
    )
    lines = extract_nmea_sentences(text)
    assert len(lines) == 4


def test_extract_with_spaces_and_mixed_newlines():
    text = (
        mk("GPRMC,000001,A,1,2,3")
        + " "
        + mk("GPGGA,000001,1,2,3")
        + "\r\n"
        + mk("GPGSA,A,3,1,2,3")
        + "\n"
        + mk("GPGSV,2,1,8,01,1,1,1")
    )
    lines = extract_nmea_sentences(text)
    assert len(lines) == 4


def test_extract_without_checksum_fallback():
    text = "$GNRMC,000001,A,1,2,3$GNGGA,000001,1,2,3"
    lines = extract_nmea_sentences(text)
    assert lines == ["$GNRMC,000001,A,1,2,3", "$GNGGA,000001,1,2,3"]


def test_slim_concatenated_keep_and_drop_behavior():
    text = "".join(
        [
            mk("GNRMC,000001,A,1,2,3"),
            mk("GNGGA,000001,1,2,3"),
            mk("GNGSA,A,3,1,2,3"),
            mk("GPGSV,2,1,8,01,1,1,1"),
            mk("GPVTG,1,2,3"),
            mk("GPGNS,1,2,3"),
            mk("GPDTM,1,2,3"),
            mk("GPXYZ,1,2,3"),
        ]
    )
    lines = extract_nmea_sentences(text)
    out, _ = slim_lines(lines, SlimOptions())
    assert len(out) == 4
    assert any("$GNGGA" in s for s in out)
    assert any("$GNRMC" in s for s in out)
    assert any("$GNGSA" in s for s in out)
    assert any("$GPGSV" in s for s in out)
