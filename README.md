## Known Issues

Currently, only NOAA and SIMPLEX are working. Other features or sources may not function as expected.


# Chirp RadioReference Scraper

This project uses a small index file, `radioref.csv`, to map RadioReference CTID pages (county/city titles) to their numeric CTID IDs. This file is required for ZIP-to-CTID mapping in the GUI and for accurate RadioReference lookups.

**If `radioref.csv` is missing or outdated, please see the [Troubleshooting](#troubleshooting) section below.**

## Quick Start


1. **Install dependencies (one command):**
   ```bash
   python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
   ```

   This will create a virtual environment (if needed), activate it, and install all requirements in one step.

2. **Run the main scraper:**
   ```bash
   .venv/bin/python chirp_scraper.py
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
