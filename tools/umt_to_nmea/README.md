# umt_to_nmea

One-time converter from UMT to standard NMEA 0183.

## Usage

python tools/umt_to_nmea/umt_to_nmea.py sample_data/xidantot3.umt -o output.nmea

python tools/umt_to_nmea/umt_to_nmea.py sample_data/xidantot3.umt -o output.nmea --start-datetime 2026-03-12T00:00:00Z

python tools/umt_to_nmea/umt_to_nmea.py sample_data/xidantot3.umt -o output.nmea --time-start 10 --time-end 120