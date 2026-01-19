## Known Issues

Currently, only NOAA and SIMPLEX are working. Other features or sources may not function as expected.


# Chirp RadioReference Scraper

A small GUI and set of scripts to scrape RadioReference (and related) data by CTID or ZIP and export CHIRP-compatible CSV files for programming radios.

This project ships several helper CSVs (NOAA, MURS, FRS/GMRS) used as fixed channel lists and as defaults for tone/DCS when scraped values are missing. These files live in `csv_files/` and should not be modified by the GUI.

## Key Features

- GUI for entering ZIP codes or full RadioReference CTID URLs and selecting bands to export.
- ZIP → CTID resolution via `radioref.csv` (preferred) with fallback geocoding when necessary.
- Scrapes RadioReference listing pages and follows detail pages to extract: frequency, mode, duplex (+/-), offset, CTCSS/DTCS (tone), and DCS polarity.
- Band selection includes explicit amateur bands `70cm` (420–450 MHz) and `2m` (144–148 MHz), plus `NOAA`, `MURS`, and `FRS/GMRS`.
- Fixed channel lists loaded from CSV files in `csv_files/`:
  - `US NOAA Weather Alert.csv` (NOAA weather channels)
  - `Murs_freq.csv` (MURS channels)
  - `FRS_GMRS_freq.csv` (FRS/GMRS channels and defaults)
- When scraped rows are missing tone/DTCS values, the app fills them from the per-band CSV defaults.
- Scanned repeater duplex normalization uses `+`/`-` symbols (not words).
- Optionally drops scanned entries that lack an `rTone` value (user-configurable behavior in the exporter).
- Exports CHIRP-compatible CSV with columns: Name, Frequency, Duplex, Offset, Tone, rToneFreq, cToneFreq, DtcsCode, DtcsPolarity, Mode, TStep, Skip, Comment.
- Menu improvements: `File -> API -> Help` ordering, `File -> Themes` (10 themes), `Help -> RadioReference`, and `Help -> How-To` which opens the local `README.md`.

## Quick Start

1. Create a Python virtual environment and install requirements (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 chirp_scraper.py --gui
```

2. Or use the included bootstrap helper:

```bash
python3 bootstrap.py --gui
```

3. Enter ZIP codes or CTID URLs in the GUI, pick bands (70cm, 2m, NOAA, MURS, FRS/GMRS), and press `Export CSV`.

Output is a CHIRP-compatible CSV you can import into programming tools.

## CSV Defaults and Fixed Lists

The app reads fixed channel and default tone/DCS values from `csv_files/`. These files are used to populate missing fields when scraping, and are intentionally treated as input-only defaults:

- `csv_files/US NOAA Weather Alert.csv` — NOAA weather channels
- `csv_files/Murs_freq.csv` — MURS channels
- `csv_files/FRS_GMRS_freq.csv` — FRS/GMRS channels and tone defaults

Do not edit these files from the GUI; they are preserved as canonical defaults.

## Advanced / Scripts

Scripts under `scripts/` provide CLI scanning tools (per-ZIP) and alternate scrapers. Example outputs are written to `media/test_<ZIP>_repeaters.csv` for per-ZIP scans.

Notable scripts:

- `scripts/scan_zip_repeaters.py` — resolve ZIP→CTID and scrape RadioReference pages for that CTID
- `scripts/scan_zip_repeaters_simple.py` — simpler scanner for quick runs
- `scripts/repeaterbook_to_chirp.py` — attempt to use RepeaterBook where available (may need further robustness)

If you provide a ZIP, the GUI will attempt to resolve the county CTID using `radioref.csv` and prefer CTID pages for scraping.

## GUI Notes

- Menu layout: `File`, `API`, `Help` (in that order).
- `File -> Themes` includes 10 selectable themes (Light, Dark, Solarized Light/Dark, Gruvbox, Monokai, Nord, Dracula, High Contrast, Classic); theme changes also recolor checkboxes and list selections.
- `File -> API` allows entering or using an encrypted RadioReference API key.
- `Help -> RadioReference` opens the RadioReference website; `Help -> How-To` opens this `README.md`.

## Donations

If you find this tool useful, please consider supporting development. Donations help cover hosting, testing, and maintenance costs.

Preferred methods and QR codes (if present) are included in the project `media/` assets and visible in the GUI donation dialog.

Thank you for your support!

## Troubleshooting

- If CTID resolution fails for a ZIP, regenerate or update `radioref.csv` with `make_radioref_list.py`.
- Scraping can be slow — some scraping paths follow detail pages; interrupting a run is safe but may leave incomplete per-ZIP CSVs in `media/`.

## Legal

This software is provided as-is. When scraping websites, ensure you follow the target site's terms of service and robots.txt. The author is not responsible for misuse.
