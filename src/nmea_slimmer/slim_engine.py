from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import re
from typing import Dict

from .checksum import with_checksum
from .nmea_parser import parse_line
from .time_shift import shift_start_datetime


@dataclass
class SlimOptions:
    keep_gga: bool = True
    keep_rmc: bool = True
    keep_gsa: bool = True
    keep_gsv: bool = True
    drop_vtg: bool = True
    drop_gns: bool = True
    drop_dtm: bool = True
    drop_unknown: bool = True
    convert_talker_to_gp: bool = False
    gsv_interval_sec: int = 0
    start_datetime_utc: datetime | None = None


@dataclass
class SlimStats:
    total_lines: int = 0
    physical_lines: int = 0
    kept_lines: int = 0
    dropped_lines: int = 0
    non_nmea_lines: int = 0
    unknown_sentences: int = 0
    extracted_sentences: int = 0
    concatenated_sentence_lines: int = 0
    no_checksum_sentences: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    output_path: str = ""
    input_size: int = 0
    output_size: int = 0


def _nmea_seconds(parsed_body: str) -> int | None:
    fields = parsed_body.split(",")
    if len(fields) < 2 or not fields[1]:
        return None
    t = fields[1].split(".")[0]
    if len(t) < 6 or not t.isdigit():
        return None
    hh, mm, ss = int(t[0:2]), int(t[2:4]), int(t[4:6])
    return hh * 3600 + mm * 60 + ss


NMEA_WITH_CHECKSUM_RE = re.compile(r"\$[A-Z]{2}[A-Z0-9]{3},[^$\r\n]*\*[0-9A-Fa-f]{2}")


def extract_nmea_sentences(text: str) -> list[str]:
    candidates: list[str] = []
    for m in NMEA_WITH_CHECKSUM_RE.finditer(text):
        candidates.append(m.group(0).strip())

    # fallback for sentences without checksum (or malformed concat edge cases)
    for chunk in text.split("$"):
        if not chunk.strip():
            continue
        candidate = "$" + chunk
        candidate = candidate.strip()
        if not candidate.startswith("$"):
            continue
        if "*" in candidate:
            continue
        if "," not in candidate:
            continue
        candidate = candidate.rstrip(" ,\t\r\n")
        candidates.append(candidate)

    # keep original order and deduplicate overlaps
    indexed: list[tuple[int, str]] = []
    cursor = 0
    for sentence in candidates:
        pos = text.find(sentence, cursor)
        if pos < 0:
            pos = text.find(sentence)
        indexed.append((pos if pos >= 0 else len(text), sentence))
        if pos >= 0:
            cursor = pos + len(sentence)
    indexed.sort(key=lambda x: x[0])

    out: list[str] = []
    for _, sentence in indexed:
        if not out or out[-1] != sentence:
            out.append(sentence)
    return out


def normalize_nmea_lines(input_path: Path) -> tuple[list[str], int]:
    text = input_path.read_text(encoding="utf-8", errors="ignore")
    physical_lines = len(text.splitlines())
    return extract_nmea_sentences(text), physical_lines


def slim_lines(lines: list[str], options: SlimOptions) -> tuple[list[str], SlimStats]:
    keep_set = {k for k, enabled in {"GGA": options.keep_gga, "RMC": options.keep_rmc, "GSA": options.keep_gsa, "GSV": options.keep_gsv}.items() if enabled}
    banned = {k for k, enabled in {"VTG": options.drop_vtg, "GNS": options.drop_gns, "DTM": options.drop_dtm}.items() if enabled}
    out: list[str] = []
    stats = SlimStats(total_lines=len(lines))
    last_gsv_bucket: int | None = None

    for line in lines:
        p = parse_line(line)
        if not p.is_nmea:
            stats.non_nmea_lines += 1
            stats.dropped_lines += 1
            continue

        t = p.sentence_type
        stats.by_type[t] = stats.by_type.get(t, 0) + 1
        if t in banned:
            stats.dropped_lines += 1
            continue

        if t not in keep_set:
            if options.drop_unknown:
                stats.unknown_sentences += 1
                stats.dropped_lines += 1
                continue

        if t == "GSV" and options.gsv_interval_sec > 0:
            sec = _nmea_seconds(p.body)
            if sec is not None:
                bucket = sec // options.gsv_interval_sec
                if last_gsv_bucket is not None and bucket == last_gsv_bucket:
                    stats.dropped_lines += 1
                    continue
                if p.body.split(",", 3)[2] == "1":
                    last_gsv_bucket = bucket

        output = p.raw
        if options.convert_talker_to_gp and len(p.body) >= 5:
            converted_body = "GP" + p.body[2:]
            output = with_checksum(converted_body)

        out.append(output)
        stats.kept_lines += 1

    stats.dropped_lines = stats.total_lines - stats.kept_lines
    if options.start_datetime_utc is not None:
        out = shift_start_datetime(out, options.start_datetime_utc)
    return out, stats


def slim_file(input_path: str, output_path: str, options: SlimOptions) -> SlimStats:
    in_path = Path(input_path)
    out_path = Path(output_path)
    lines, physical_lines = normalize_nmea_lines(in_path)
    result, stats = slim_lines(lines, options)
    out_path.write_text("\n".join(result) + ("\n" if result else ""), encoding="utf-8")
    stats.physical_lines = physical_lines
    stats.extracted_sentences = len(lines)
    stats.no_checksum_sentences = sum(1 for line in lines if "*" not in line)
    stats.concatenated_sentence_lines = max(0, stats.extracted_sentences - stats.physical_lines)
    stats.output_path = str(out_path)
    stats.input_size = in_path.stat().st_size
    stats.output_size = out_path.stat().st_size
    return stats
