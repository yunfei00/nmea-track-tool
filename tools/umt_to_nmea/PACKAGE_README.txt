UMT to NMEA converter
=====================

This package contains the Windows command-line converter for UMT files.

The converter is not a double-click GUI app. Run it from PowerShell or
Command Prompt with an input file and an output path.

Example:

  .\umt-to-nmea.exe sample_data\xidantot3.umt -o output.nmea

Example with an explicit UTC start datetime:

  .\umt-to-nmea.exe sample_data\xidantot3.umt -o output.nmea --start-datetime 2026-03-12T00:00:00Z

Example with a relative-time window:

  .\umt-to-nmea.exe sample_data\xidantot3.umt -o output.nmea --time-start 10 --time-end 120

If you double-click umt-to-nmea.exe, Windows may open and close a console
window immediately because no command-line arguments were provided.
