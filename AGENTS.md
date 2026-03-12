# Project goal

This repository is for NMEA track tools.

Current phase:
implement a one-time Python converter from UMT to NMEA.

The converter should be placed under:

tools/umt_to_nmea/umt_to_nmea.py

## Scope for current phase

Only implement:
UMT -> NMEA

Do not implement GUI in this phase.
Do not implement PySide6 in this phase.

## UMT format

column0 : relative time in seconds
column3 : latitude
column4 : longitude
column5 : altitude in meters

## Output

Generate standard NMEA 0183 text file.

At minimum, output:
- GPRMC
- GPGGA

## CLI behavior

Supported examples:

python tools/umt_to_nmea/umt_to_nmea.py sample_data/xidantot3.umt -o output.nmea

python tools/umt_to_nmea/umt_to_nmea.py sample_data/xidantot3.umt -o output.nmea --start-datetime 2026-03-12T00:00:00Z

python tools/umt_to_nmea/umt_to_nmea.py sample_data/xidantot3.umt -o output.nmea --time-start 10 --time-end 120

## Rules

- Prefer Python 3.11 standard library
- Keep implementation simple and readable
- Detect whether lat/lon are radians or degrees
- Estimate speed and course from adjacent points
- Recompute NMEA checksum
- Print useful logs