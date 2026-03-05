
# Chirp RadioReference Scraper 🚀

![ChirpScrape screenshot](https://raw.githubusercontent.com/Drizztdowhateva/Chirp_Scrape/main/media/26Feb_16_ChirpScrape.png)

This project uses a small index file, `radioref.csv`, to map RadioReference CTID pages (county/city titles) to their numeric CTID IDs. This file is required for ZIP-to-CTID mapping in the GUI and for accurate RadioReference lookups.

**If `radioref.csv` is missing or outdated, please see the [Troubleshooting](#troubleshooting) section below.**

**📚 Documentation**: See [README_ENHANCEMENTS.md](README_ENHANCEMENTS.md) for complete feature documentation, and [CHANGELOG.md](CHANGELOG.md) for version history and updates.

## Quick Start ✅

1. **One-step runtime (recommended)**

   Run the `ChirpScrape` launcher to create/repair the virtual environment, install dependencies, and launch the app in GUI mode by default (no switches):

   Linux / macOS:

   ```bash
   ./ChirpScrape
   # or: python3 ChirpScrape
   ```

   Windows (PowerShell):

   ```powershell
   python ChirpScrape
   ```

   Windows (cmd.exe):

   ```cmd
   python ChirpScrape
   ```

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

## One Runtime File

Primary runtime command (GUI default, no switches):

```bash
./ChirpScrape
```

Runtime launchers are kept in the main project directory for easy discovery:
- `ChirpScrape`
- `bootstrap.py`

Use `bootstrap.py` as the single runtime entrypoint for install/run/test/security:

```bash
python3 bootstrap.py run        # install deps, then run app
python3 bootstrap.py install    # install deps only
python3 bootstrap.py test       # syntax + unittest smoke tests
python3 bootstrap.py security   # lightweight static security scan
python3 bootstrap.py package    # build one-time distributable for this OS
python3 bootstrap.py all        # install + security + test + run
```

Legacy flags still work (`--install-only`, `--test`, `--security-check`, `--gui`).

## Build App, DMG, EXE (One-Time Packaging)

Packaging is platform-native. Build on the target OS:

### Linux Onefile Binary

```bash
./scripts/build_linux_onefile.sh
```

Output:
- `dist/ChirpScrape`

### macOS App + DMG

```bash
./scripts/build_macos_app_dmg.sh
```

Outputs:
- `dist/ChirpScrape.app`
- `dist/ChirpScrape.dmg`

### Windows EXE

Run in PowerShell:

```powershell
./scripts/build_windows_exe.ps1
```

Output:
- `dist/ChirpScrape.exe`

Notes:
- `.app`/`.dmg` must be built on macOS.
- `.exe` must be built on Windows.
- A Linux build was generated in this workspace and verified with `--help` at `dist/ChirpScrape`.

## Donations 🙏

Developing and maintaining open source software takes significant time and resources. Your support helps cover development, testing, and hosting costs. Every contribution makes a difference!

**🎁 Donation Portal**: A professional donation page appears on first launch. You can dismiss it and access it anytime via **Help → Contact → Donations** in the app menu.

**Thank you for considering a donation!**

### Why Donate? 💡
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

## Troubleshooting 🛠️

### Python Environment & Dependency Issues 🐍

**If you encounter numpy/pandas import errors:**

ChirpScrape now supports Python 3.13 with properly compatible dependencies:
- **numpy 2.4.2+** - Required for Python 3.13 compatibility
- **pandas 3.0.0+** - Updated for latest numpy and Python versions

**Solution:**
If you already have an old venv, start fresh:

```bash
# Remove old environment
rm -rf .venv

# Create new environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate  # (or .\.venv\Scripts\Activate.ps1 on Windows)
pip install -r requirements.txt
```

The `bootstrap.py` script handles this automatically, so using it is recommended for a clean installation.

### RadioReference Index File (`radioref.csv`) 📂

If you see errors or missing data related to RadioReference lookups, or if `radioref.csv` is missing or outdated, you need to (re)generate the index file. Use the helper script below:

#### Generate or Update `radioref.csv`

Run this command to crawl RadioReference and build or refresh the index:

```bash
./.venv/bin/python make_radioref_list.py --start-id 1 --max-id 3000 --append
```

**Notes:**
- The crawl can take a long time; use `--delay` to be polite and `--stop-after-missing` to stop after many consecutive misses.
- `chirp_rr_zip_scraper.py` will still run without `radioref.csv`, but ZIP lookups that depend on the index may show "(no ctid)" and fall back to ZIP-level RadioReference pages.

See `README.txt` for additional project notes.

**Help → Firmware submenu:** New firmware unlock resources (Baofeng unlock guides and firmware links) are available in the app under the **Help → Firmware** menu. See the in-app Help for step-by-step links and resources.

**Advertising & Media:** Advertising copy and media (including the Facebook advert) are available in the `Advert/` folder. See `Advert/Facebook.md` for Facebook-specific ad content.

## Legal ⚖️

This software is provided as-is. When scraping websites, ensure you follow the target site's terms of service and robots.txt. The author is not responsible for misuse.

