# umt_to_nmea

One-time converter from UMT to standard NMEA 0183.

## Usage

python tools/umt_to_nmea/umt_to_nmea.py sample_data/xidantot3.umt -o output.nmea

python tools/umt_to_nmea/umt_to_nmea.py sample_data/xidantot3.umt -o output.nmea --start-datetime 2026-03-12T00:00:00Z

python tools/umt_to_nmea/umt_to_nmea.py sample_data/xidantot3.umt -o output.nmea --time-start 10 --time-end 120

python tools/umt_to_nmea/umt_to_nmea.py sample_data/xidantot3.umt -o output.nmea --sample-step 10

## Behavior

- Reads UMT `column0` as relative time in seconds.
- Reads UMT `column3` as latitude and `column4` as longitude.
- Reads UMT `column5` as altitude in meters.
- If `--start-datetime` is omitted, the generated NMEA time starts at `00:00:00`.
- `--time-start` and `--time-end` filter rows by relative time.
- `--sample-step N` keeps every `N`th input row after time filtering.
- The converter validates latitude in `[-90, 90]` and longitude in `[-180, 180]`.
- The converter prints logs for total rows read, rows after filtering, rows written, and the number of generated NMEA sentences.
