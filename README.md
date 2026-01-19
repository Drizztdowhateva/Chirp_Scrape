## Known Issues

Currently, only NOAA and SIMPLEX are working. Other features or sources may not function as expected.


# Chirp RadioReference Scraper

This project uses a small index file, `radioref.csv`, to map RadioReference CTID pages (county/city titles) to their numeric CTID IDs. This file is required for ZIP-to-CTID mapping in the GUI and for accurate RadioReference lookups.

**If `radioref.csv` is missing or outdated, please see the [Troubleshooting](#troubleshooting) section below.**

## Quick Start

1. **One-step bootstrap (recommended)**

   Run the provided `bootstrap.py` to create a virtual environment, install dependencies, and launch the app. This is the easiest cross-platform method:

   Linux / macOS:

   ```bash
   python3 bootstrap.py --gui
   ```

   Windows (PowerShell):

   ```powershell
   python bootstrap.py --gui
   ```

   Windows (cmd.exe):

   ```cmd
   python bootstrap.py --gui
   ```

   If you only want to install dependencies without launching the GUI, pass `--install-only`.

2. **Manual setup (alternative)**

   If you prefer to create the venv yourself, follow the platform-specific steps below.

   Linux / macOS (bash/zsh):

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python3 chirp_scraper.py --gui
   ```

   Windows (PowerShell):

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   python chirp_scraper.py --gui
   ```

   Windows (cmd.exe):

   ```cmd
   python -m venv .venv
   .\.venv\Scripts\activate.bat
   pip install -r requirements.txt
   python chirp_scraper.py --gui
   ```

3. **Check output:**
   - Output files will be generated in the project directory (e.g., `chirp_output.csv`).

## Donations

Developing and maintaining open source software takes significant time and resources. Your support helps cover development, testing, and hosting costs. Every contribution makes a difference!

**Thank you for considering a donation!**

### Why Donate?
- Open source software fosters innovation and collaboration.
- Supports learning and skill development for programmers.
- Provides cost-effective solutions for everyone.
- Drives technological advancement and builds strong communities.

### Choose Your Donation Method

#### PayPal
[![PayPal QR Code](https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=https%3A%2F%2Fpaypal.me%2FDr1zztD)](https://paypal.me/Dr1zztD)

[paypal.me/Dr1zztD](https://paypal.me/Dr1zztD)

#### Cash App
<a href="https://cash.app/$teerRight" target="_blank">
   <img src="https://cash.app/qr/$teerRight" alt="Cash App QR Code" width="200" />
</a>

[$teerRight](https://cash.app/$teerRight)

---

## Troubleshooting

### RadioReference Index File (`radioref.csv`)

If you see errors or missing data related to RadioReference lookups, or if `radioref.csv` is missing or outdated, you need to (re)generate the index file. Use the helper script below:

#### Generate or Update `radioref.csv`

Run this command to crawl RadioReference and build or refresh the index:

```bash
./.venv/bin/python make_radioref_list.py --start-id 1 --max-id 20000 --append
```

**Notes:**
- The crawl can take a long time; use `--delay` to be polite and `--stop-after-missing` to stop after many consecutive misses.
- `chirp_rr_zip_scraper.py` will still run without `radioref.csv`, but ZIP lookups that depend on the index may show "(no ctid)" and fall back to ZIP-level RadioReference pages.

See `README.txt` for additional project notes.

## Legal

This software is provided as-is. Use at your own risk. The author is not responsible for misuse. When scraping websites, ensure you follow the target site's terms of service.
