from __future__ import annotations

import re
from dataclasses import dataclass

NMEA_RE = re.compile(r"^\$(?P<body>[^*$]+)(?:\*(?P<checksum>[0-9A-Fa-f]{2}))?$")


@dataclass
class ParsedLine:
    raw: str
    is_nmea: bool
    body: str = ""
    talker: str = ""
    sentence_type: str = ""



def parse_line(line: str) -> ParsedLine:
    raw = line.rstrip("\n\r")
    m = NMEA_RE.match(raw)
    if not m:
        return ParsedLine(raw=raw, is_nmea=False)
    body = m.group("body")
    head = body.split(",", 1)[0]
    if len(head) < 5:
        return ParsedLine(raw=raw, is_nmea=True, body=body)
    return ParsedLine(
        raw=raw,
        is_nmea=True,
        body=body,
        talker=head[:2],
        sentence_type=head[2:5],
    )
