# nmea-track-tool

`nmea-track-tool` is a small Python project for working with NMEA 0183 track data.

It currently includes:

- a one-time UMT -> NMEA converter
- a reusable core pipeline for parsing, validating, segmenting, and summarizing tracks
- a command-line analyzer
- a PySide6 desktop viewer with summary, table, map, delete/reset workflow, and export actions

## Project Layout

- `tools/umt_to_nmea/`
  - one-time UMT -> NMEA converter
- `core/`
  - reusable parsing, validation, segmentation, metrics, and pipeline code
- `cli/`
  - command-line entry points
- `gui/`
  - PySide6 desktop viewer
- `sample_data/`
  - small demo files for testing and exploration

## Installation

Python 3.11 or newer is recommended.

### 1. Create a virtual environment

Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

macOS / Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install GUI dependency

The core pipeline and CLI use the Python standard library.
The desktop viewer requires `PySide6`.

```bash
pip install PySide6
```

### 3. Run tests

```bash
python -m unittest discover -s tests -t .
```

## Sample Data

- `sample_data/demo_track.nmea`
  - small demo NMEA track for the CLI and GUI
- `sample_data/xidantot3.umt`
  - raw UMT input for the converter

## CLI Usage

Analyze an NMEA file:

```bash
python -m cli.nmea_track_cli analyze sample_data/demo_track.nmea
```

Analyze and export the current point list and summary:

```bash
python -m cli.nmea_track_cli analyze sample_data/demo_track.nmea --export-points-csv output/demo_points.csv --export-summary-json output/demo_summary.json
```

Convert a UMT file to NMEA:

```bash
python tools/umt_to_nmea/umt_to_nmea.py sample_data/xidantot3.umt -o output/converted_track.nmea
```

Convert a UMT file with an explicit UTC start datetime:

```bash
python tools/umt_to_nmea/umt_to_nmea.py sample_data/xidantot3.umt -o output/converted_track.nmea --start-datetime 2026-03-12T00:00:00Z
```

Convert only a time window and sample every 10th point:

```bash
python tools/umt_to_nmea/umt_to_nmea.py sample_data/xidantot3.umt -o output/converted_track_window.nmea --time-start 10 --time-end 120 --sample-step 10
```

## GUI Usage

Start the desktop viewer:

```bash
python -m gui.app
```

Then:

1. Click `Open NMEA File` or use the `File` menu.
2. Open `sample_data/demo_track.nmea`.
3. Review the summary panel, point table, and map view.
4. Optionally delete bad points, reset to original data, or export the current working dataset.

## Current GUI Features

- open an NMEA file through the existing core pipeline
- summary panel with point counts, segment count, distance, duration, and speeds
- point table with invalid rows highlighted
- map view with track polyline, start/end markers, and invalid-point markers
- delete selected points from the working dataset
- reset the working dataset back to the original loaded data
- export cleaned NMEA, points CSV, and summary JSON

## Example Commands

Quick CLI check:

```bash
python -m cli.nmea_track_cli analyze sample_data/demo_track.nmea
```

GUI startup:

```bash
python -m gui.app
```

Full test suite:

```bash
python -m unittest discover -s tests -t .
```

## GUI Screenshot Placeholder

Placeholder for the first public-release screenshot of the desktop viewer:

- main window with summary panel
- point table with invalid rows highlighted
- map view showing track, start/end markers, and invalid-point markers

## Notes

- The GUI uses the existing `core.pipeline` module and does not duplicate track parsing logic.
- If your active interpreter cannot load Qt correctly, using the project virtual environment is the safest option:

```powershell
.venv\Scripts\python.exe -m gui.app
```
