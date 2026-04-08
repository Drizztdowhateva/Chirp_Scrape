# freqfinder.py
# TX is ENABLED on repeaters via Duplex +/-
#
# Note: This script uses a small local index file `radioref.csv` which maps
# RadioReference CTID pages (county/city names) to numeric IDs. The helper
# script `make_radioref_list.py` compiles that index by crawling
# https://www.radioreference.com/db/browse/ctid/<id>/ham pages and writing
# `radioref.csv`. If `radioref.csv` is missing or you want to refresh RadioReference
# data, run `make_radioref_list.py` before using this program.
#
# References & Acknowledgements:
#   RadioReference.com    — frequency database (https://www.radioreference.com)
#   CHIRP                 — open-source radio programming software (https://chirp.danplanet.com)
#                           GitHub repo owner: Dan Smith (KK7DS) — https://github.com/kk7ds/chirp
#                           Lead developer/maintainer: Jim Unroe (KC9HI)
#   John Miklor (WA9QJV) — comprehensive CHIRP programming guides & Baofeng resources
#                           https://www.miklor.com/CHIRP/index.php

import subprocess
import os
import sys

def _ensure_project_venv_and_requirements():
    here = os.path.dirname(os.path.abspath(__file__))
    venv_dir = os.path.join(here, '.venv')
    if os.name == 'nt':
        venv_py = os.path.join(venv_dir, 'Scripts', 'python.exe')
    else:
        venv_py = os.path.join(venv_dir, 'bin', 'python')
    reqs = os.path.join(here, 'requirements.txt')

    if not os.path.exists(venv_py):
        try:
            print('Creating virtual environment...')
            subprocess.check_call([sys.executable, '-m', 'venv', venv_dir])
        except Exception:
            pass

    need_reexec = False
    try:
        import pandas, bs4, requests
    except Exception:
        try:
            print('Installing required Python packages...')
            subprocess.check_call([venv_py, '-m', 'pip', 'install', '--upgrade', 'pip'])
            if os.path.exists(reqs):
                subprocess.check_call([venv_py, '-m', 'pip', 'install', '-r', reqs])
            else:
                subprocess.check_call([venv_py, '-m', 'pip', 'install', 'pandas', 'requests', 'beautifulsoup4'])
            need_reexec = True
        except Exception:
            need_reexec = False

    try:
        if need_reexec or os.path.realpath(sys.executable) != os.path.realpath(venv_py):
            os.execv(venv_py, [venv_py] + sys.argv)
    except Exception:
        pass

# Bootstrapping step is optional and disabled by default to avoid
# attempting system package installation in managed environments.
# Call `_ensure_project_venv_and_requirements()` manually if needed.

import re
import sys
import os
import time
import argparse

# Import dependencies after bootstrapping
import requests
import pandas as pd
from bs4 import BeautifulSoup
try:
    import tkinter as tk
    from tkinter import simpledialog, messagebox
    _TK_AVAILABLE = True
except Exception:
    _TK_AVAILABLE = False


def gui_session_available():
    """Return True when tkinter is importable.

    We intentionally avoid strict env-var checks because desktop terminals can
    vary across X11/Wayland/Mir/WSL integrations. Actual GUI availability is
    determined by attempting to create windows and catching runtime errors.
    """
    return _TK_AVAILABLE

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36'
}
HTTP_SESSION = requests.Session()
HTTP_SESSION.headers.update(DEFAULT_HEADERS)

RADIO_BROWSER_API_BASE = 'https://de1.api.radio-browser.info/json'
DEFAULT_SAVE_DIR = os.path.expanduser('~/Documents')
DEFAULT_OUTPUT_FILE = os.path.join(DEFAULT_SAVE_DIR, 'freqfinder_output.csv')
SETTINGS_FILE = os.path.expanduser('~/.freqfinder_settings.json')

REQUEST_DELAY_SECONDS = float(os.environ.get('FREQFINDER_REQUEST_DELAY', '0') or 0)
_last_http_get_timestamp = None

DEFAULT_PERSISTENT_SETTINGS = {
    'selected_model': 'Generic',
    'selected_source': 'RadioReference',
    'customization_level': 'Default',
    'scanner_mode': 0,
    'frs_gmrs_unlock': 0,
}


def load_persistent_settings():
    try:
        if os.path.exists(SETTINGS_FILE):
            import json
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as sf:
                data = json.load(sf)
            if isinstance(data, dict):
                return {**DEFAULT_PERSISTENT_SETTINGS, **data}
    except Exception:
        pass
    return dict(DEFAULT_PERSISTENT_SETTINGS)


def save_persistent_settings(data):
    try:
        import json
        safe = {k: data.get(k, DEFAULT_PERSISTENT_SETTINGS.get(k)) for k in DEFAULT_PERSISTENT_SETTINGS}
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as sf:
            json.dump(safe, sf, indent=2)
    except Exception:
        pass


def http_get(url, timeout=15, headers=None, delay=None, **kwargs):
    """Shared HTTP GET helper using one session for connection reuse.

    Supports optional delays between remote requests to avoid rate limiting
    and reduce anti-scraping detection.
    """
    global _last_http_get_timestamp
    if delay is None:
        delay = REQUEST_DELAY_SECONDS
    if delay and _last_http_get_timestamp is not None:
        elapsed = time.monotonic() - _last_http_get_timestamp
        if elapsed < delay:
            time.sleep(delay - elapsed)

    req_headers = DEFAULT_HEADERS if headers is None else headers
    attempts = 3
    backoff = 1.0
    for attempt in range(attempts):
        try:
            resp = HTTP_SESSION.get(url, headers=req_headers, timeout=timeout, **kwargs)
        except requests.RequestException as exc:
            if attempt + 1 < attempts:
                time.sleep(backoff)
                backoff *= 2
                continue
            raise

        _last_http_get_timestamp = time.monotonic()
        if resp.status_code == 405 and 'Human Verification' in resp.text:
            raise RuntimeError(
                'RadioReference blocked access with human verification. '
                'This means automated scraping is not currently allowed from this environment. '
                'Use the Radio Browser source in Preferences, or provide a direct API-backed source.'
            )
        if resp.status_code in (429, 503):
            if attempt + 1 < attempts:
                time.sleep(backoff)
                backoff *= 2
                continue
        if resp.status_code == 403 and attempt + 1 < attempts:
            time.sleep(backoff)
            backoff *= 2
            continue
        resp.raise_for_status()
        return resp

    raise RuntimeError(f'HTTP GET failed for {url} after {attempts} attempts')

# Try to load an encrypted RadioReference API key (optional)
RR_API_KEY = None
try:
    from rr_api import load_api_key
    enc_path = os.path.join(os.path.dirname(__file__), 'rr_api.enc')
    passphrase = os.environ.get('RR_API_PASS')
    if passphrase and os.path.exists(enc_path):
        try:
            RR_API_KEY = load_api_key(passphrase, enc_path)
        except Exception:
            RR_API_KEY = None
except Exception:
    RR_API_KEY = None

# Prefer an env-provided API key if present; otherwise load encrypted key if possible;
# only create the built-in encrypted key when no user key is provided.
try:
    # If user explicitly set RR_API_KEY env var, respect it and do nothing else
    env_key = os.environ.get('RR_API_KEY')
    if env_key:
        RR_API_KEY = env_key
    else:
        import rr_api as _rr_api
        enc_path = os.path.join(os.path.dirname(__file__), 'rr_api.enc')
        passfile = os.path.abspath(os.path.join(os.path.dirname(__file__), '.rr_api_pass'))
        # If RR_API_PASS is set and enc exists, try to load
        passphrase = os.environ.get('RR_API_PASS')
        if passphrase and os.path.exists(enc_path):
            try:
                RR_API_KEY = _rr_api.load_api_key(passphrase, enc_path)
            except Exception:
                RR_API_KEY = None
        else:
            # If enc exists and we can read passfile, try that
            if os.path.exists(enc_path) and os.path.exists(passfile) and RR_API_KEY is None:
                try:
                    with open(passfile, 'r', encoding='utf-8') as pf:
                        p = pf.read().strip()
                    if p:
                        try:
                            RR_API_KEY = _rr_api.load_api_key(p, enc_path)
                            os.environ['RR_API_PASS'] = p
                        except Exception:
                            RR_API_KEY = None
                except Exception:
                    RR_API_KEY = None
            # No built-in key is bundled; users must supply their own via RR_API_KEY
            # or RR_API_PASS environment variables, or through the Preferences dialog.
            # (Hardcoding an API key in source is a security risk and has been removed.)
except Exception:
    pass

# NOAA weather channels are provided in csv_files/US NOAA Weather Alert.csv
NOAA_CSV = os.path.join(os.path.dirname(__file__), 'csv_files', 'US NOAA Weather Alert.csv')
NOAA_FREQS = []
try:
    import csv as _csv
    with open(NOAA_CSV, newline='', encoding='utf-8') as _fh:
        reader = _csv.DictReader(_fh)
        for row in reader:
            name = (row.get('Name') or row.get('name') or '').strip()
            freq_s = (row.get('Frequency') or row.get('frequency') or '').strip()
            if not freq_s:
                continue
            try:
                freq = float(freq_s)
            except Exception:
                continue
            tone = (row.get('rToneFreq') or row.get('rTone') or row.get('Tone') or '').strip()
            NOAA_FREQS.append((name, freq, tone, row))
except Exception:
    NOAA_FREQS = []

# MURS fixed channels are provided in csv_files/Murs_freq.csv
MURS_CSV = os.path.join(os.path.dirname(__file__), 'csv_files', 'Murs_freq.csv')
MURS_FREQS = []
try:
    import csv as _csv
    with open(MURS_CSV, newline='', encoding='utf-8') as _fh:
        reader = _csv.DictReader(_fh)
        for row in reader:
            name = (row.get('Name') or row.get('name') or '').strip()
            freq_s = (row.get('Frequency') or row.get('frequency') or '').strip()
            if not freq_s:
                continue
            try:
                freq = float(freq_s)
            except Exception:
                continue
            tone = (row.get('rToneFreq') or row.get('rTone') or row.get('Tone') or '').strip()
            MURS_FREQS.append((name, freq, tone, row))
except Exception:
    MURS_FREQS = []

# FRS/GMRS fixed channels are provided in csv_files/FRS_GMRS_freq.csv
FRS_GMRS_CSV = os.path.join(os.path.dirname(__file__), 'csv_files', 'FRS_GMRS_freq.csv')
FRS_GMRS_FREQS = []
try:
    import csv as _csv
    with open(FRS_GMRS_CSV, newline='', encoding='utf-8') as _fh:
        reader = _csv.DictReader(_fh)
        for row in reader:
            name = (row.get('Name') or row.get('name') or '').strip()
            freq_s = (row.get('Frequency') or row.get('frequency') or '').strip()
            if not freq_s:
                continue
            try:
                freq = float(freq_s)
            except Exception:
                continue
            duplex = (row.get('Duplex') or '').strip()
            # prefer explicit rToneFreq if present, otherwise Tone column
            tone = (row.get('rToneFreq') or row.get('rTone') or row.get('Tone') or '').strip()
            FRS_GMRS_FREQS.append((name, freq, duplex, tone, row))
except Exception:
    FRS_GMRS_FREQS = []

DEFAULT_PAGES = {
    "Cook County, Illinois": "https://www.radioreference.com/db/browse/ctid/606/ham",
}

# Band definitions for GUI selection and filtering (ranges in MHz)
BAND_RANGES = {
    '70cm': [(420.0, 450.0)],
    '2m': [(144.0, 148.0)],
    'NOAA': [(162.4, 162.55)],
    'MURS': [(151.82, 154.6)],
    'FRS/GMRS': [(462.0, 467.0)],
    # Emergency: heuristic ranges covering common public-safety analog bands
    'Emergency': [
        (30.0, 50.0),    # Low VHF (some legacy)
        (138.0, 174.0),  # VHF high-band (public safety)
        (380.0, 470.0),  # UHF public safety
        (700.0, 900.0),  # 700/800 MHz public-safety ranges
    ],
}

# Radio Model Definitions with Supported Features
RADIO_MODELS = {
    'Generic': {
        'name': 'Generic Radio (Default)',
        'supports_tone': True,
        'supports_p25': False,
        'supports_edacs': False,
        'supports_dtcs': True,
        'supports_duplex': True,
        'supports_offset': True,
        'supports_step': True,
        'supports_mode': True,
        'supports_skip': True,
        'supports_comment': True,
        'max_channels': 10000,
        'tone_frequencies': True,
        'description': 'Compatible with most CHIRP-supported radios'
    },

    'Baofeng_UV5R': {
        'name': 'Baofeng UV-5R',
        'supports_tone': True,
        'supports_p25': False,
        'supports_edacs': False,
        'supports_dtcs': True,
        'supports_duplex': True,
        'supports_offset': True,
        'supports_step': True,
        'supports_mode': True,
        'supports_skip': True,
        'supports_comment': True,
        'max_channels': 128,
        'tone_frequencies': True,
        'description': 'Popular budget dual-band UHF/VHF handheld (includes UV-5R Mini variant)'
    },

    'Baofeng_UV82': {
        'name': 'Baofeng UV-82',
        'supports_tone': True,
        'supports_p25': False,
        'supports_edacs': False,
        'supports_dtcs': True,
        'supports_duplex': True,
        'supports_offset': True,
        'supports_step': True,
        'supports_mode': True,
        'supports_skip': True,
        'supports_comment': True,
        'max_channels': 128,
        'tone_frequencies': True,
        'description': 'Rugged dual-band UHF/VHF handheld - Waterproof variant'
    },
    'Motorola': {
        'name': 'Motorola (Professional)',
        'supports_tone': True,
        'supports_p25': True,
        'supports_edacs': False,
        'supports_dtcs': True,
        'supports_duplex': True,
        'supports_offset': True,
        'supports_step': True,
        'supports_mode': True,
        'supports_skip': True,
        'supports_comment': True,
        'supports_color_code': True,
        'supports_digital_mode': True,
        'max_channels': 1000,
        'tone_frequencies': True,
        'description': 'Professional grade digital/analog radio'
    },
    'Kenwood': {
        'name': 'Kenwood (VHF/UHF)',
        'supports_tone': True,
        'supports_p25': True,
        'supports_edacs': False,
        'supports_dtcs': True,
        'supports_duplex': True,
        'supports_offset': True,
        'supports_step': True,
        'supports_mode': True,
        'supports_skip': True,
        'supports_comment': True,
        'max_channels': 500,
        'tone_frequencies': True,
        'description': 'Kenwood mobile/portable radios'
    },
    'Motorola_APX': {
        'name': 'Motorola APX Series',
        'supports_tone': True,
        'supports_p25': True,
        'supports_edacs': False,
        'supports_dtcs': True,
        'supports_duplex': True,
        'supports_offset': True,
        'supports_step': True,
        'supports_mode': True,
        'supports_skip': True,
        'supports_comment': True,
        'supports_digital_mode': True,
        'max_channels': 2000,
        'tone_frequencies': True,
        'description': 'Professional P25-capable Motorola radios (APX series)'
    },
    'Icom_P25': {
        'name': 'Icom P25-capable',
        'supports_tone': True,
        'supports_p25': True,
        'supports_edacs': False,
        'supports_dtcs': True,
        'supports_duplex': True,
        'supports_offset': True,
        'supports_step': True,
        'supports_mode': True,
        'supports_skip': True,
        'supports_comment': True,
        'supports_digital_mode': True,
        'max_channels': 2000,
        'tone_frequencies': True,
        'description': 'Icom radios with P25 capability'
    }
}

# Customization Levels (Default to High Quality)
CUSTOMIZATION_LEVELS = {
    'Default': {
        'include_comment': True,
        'include_tone': True,
        'include_offset': True,
        'include_skip': False,
        'validate_frequencies': True,
        'description': 'Basic settings with essential features'
    },
    'Standard': {
        'include_comment': True,
        'include_tone': True,
        'include_offset': True,
        'include_skip': True,
        'validate_frequencies': True,
        'remove_duplicates': True,
        'description': 'Standard settings with extended features'
    },
    'Advanced': {
        'include_comment': True,
        'include_tone': True,
        'include_offset': True,
        'include_skip': True,
        'include_tone_decode': True,
        'validate_frequencies': True,
        'remove_duplicates': True,
        'sort_by_frequency': True,
        'description': 'Advanced customization for power users'
    },
    'High Quality': {
        'include_comment': True,
        'include_tone': True,
        'include_offset': True,
        'include_skip': True,
        'include_tone_decode': True,
        'validate_frequencies': True,
        'remove_duplicates': True,
        'sort_by_frequency': True,
        'optimize_step_sizes': True,
        'add_metadata': True,
        'description': 'Maximum quality with all optimization features'
    }
}

# Application Settings for Startup and Safety
APP_SETTINGS = {
    'text_startup': {
        'default': False,
        'label': 'Text Mode Startup (CLI)',
        'description': 'Start in text/command-line mode instead of GUI'
    },
    'disable_startup_tips': {
        'default': False,
        'label': 'Disable Startup Tips',
        'description': 'Skip the Getting Started guide on launch'
    },
    'confirm_export': {
        'default': True,
        'label': 'Confirm Before Export',
        'description': 'Ask for confirmation before exporting channels'
    },
    'backup_before_save': {
        'default': True,
        'label': 'Auto Backup Before Save',
        'description': 'Automatically backup CSV files before overwriting'
    },
    'safe_frequency_check': {
        'default': True,
        'label': 'Enable Safe Frequency Validation',
        'description': 'Validate all frequencies against band limits'
    },
    'warn_channel_limit': {
        'default': True,
        'label': 'Warn When Exceeding Channel Limit',
        'description': 'Alert when imported channels exceed radio capacity'
    },
}

# Consolidate valid frequency bands from BAND_RANGES so MURS/GMRS/NOAA are included
VALID_BANDS = []
for ranges in BAND_RANGES.values():
    for lo, hi in ranges:
        VALID_BANDS.append((float(lo), float(hi)))

def valid_freq(f):
    try:
        fv = float(f)
    except Exception:
        return False
    return any(lo <= fv <= hi for lo, hi in VALID_BANDS)

def scrape_rr(url):
    """Fetch `url` and return parsed frequency rows via parse_rr_html."""
    resp = http_get(url, timeout=15)
    return parse_rr_html(resp.text)


def parse_rr_html(html_text):
    """Parse RadioReference HTML (string) and return list of tuples like scrape_rr."""
    soup = BeautifulSoup(html_text, "html.parser")
    out = []
    for table in soup.select("table.rrdbTable"):
        for tr in table.select("tbody tr"):
            td = tr.find_all("td")
            if len(td) < 3:
                continue
            ftext = td[0].text.strip()
            try:
                f = float(ftext)
            except Exception:
                continue
            if not valid_freq(f):
                continue
            callsign = td[2].text.strip() if len(td) > 2 else ""
            tone = td[4].text.strip() if len(td) > 4 else ""
            desc = ""
            for idx in (7, 6, 3):
                if idx < len(td):
                    txt = td[idx].text.strip()
                    if txt:
                        desc = txt
                        break
            name = callsign or desc or ""
            duplex_hint = None
            offset_hint = None
            try:
                other_texts = ' '.join(td[i].text.strip() for i in range(1, len(td)))
                if re.search(r'\b\+\b', other_texts) or re.search(r'\bplus\b', other_texts, re.I):
                    duplex_hint = '+'
                elif re.search(r'\b\-\b', other_texts) or re.search(r'\bminus\b', other_texts, re.I):
                    duplex_hint = '-'
                nums = re.findall(r'([0-9]+\.[0-9]+)', other_texts)
                for n in nums:
                    try:
                        nv = float(n)
                    except Exception:
                        continue
                    if abs(nv - 0.6) < 0.001 or abs(nv - 5.0) < 0.01:
                        offset_hint = nv
                        m = re.search(r'([\+\-])\s*' + re.escape(n), other_texts)
                        if m:
                            duplex_hint = m.group(1)
                        break
            except Exception:
                pass
            out.append((name, f, tone, duplex_hint, offset_hint))
    return out


def fetch_freqs_for_page(url):
    """Try to fetch frequency rows for a given RadioReference URL.

    If an API key is available (RR_API_KEY), request the page with the
    `X-API-Key` header and parse the returned HTML. On any failure, fall
    back to `scrape_rr(url)`.
    """
    # If we have an API key and the URL contains a CTID, try SOAP database API first
    try:
        if RR_API_KEY:
            # attempt SOAP when CTID is available in the URL
            m = re.search(r'/db/browse/ctid/(\d+)', url)
            if m:
                ctid = m.group(1)
                try:
                    import rr_api as _rr_api
                    recs = _rr_api.try_get_repeaters_via_soap(RR_API_KEY, ctid)
                    if recs:
                        # convert records to (name,freq,tone,duplex_hint,offset_hint)
                        out = []
                        for r in recs:
                            # try common fields
                            name = r.get('Name') or r.get('callsign') or r.get('CallSign') or r.get('NameLong') or r.get('Description') or ''
                            freq = None
                            for fk in ('Frequency','Freq','frequency','f'):
                                if fk in r and r.get(fk) not in (None, ''):
                                    try:
                                        freq = float(r.get(fk))
                                        break
                                    except Exception:
                                        pass
                            tone = r.get('Tone') or r.get('tone') or ''
                            duplex_hint = r.get('Duplex') if 'Duplex' in r else None
                            offset_hint = r.get('Offset') if 'Offset' in r else None
                            if freq is not None:
                                out.append((name, freq, tone, duplex_hint, offset_hint))
                        if out:
                            return out
                except Exception:
                    pass
            # fallback to header-based HTML fetch
            headers = {'X-API-Key': RR_API_KEY}
            resp = http_get(url, headers=headers, timeout=15)
            if 'rrdbTable' in resp.text:
                return parse_rr_html(resp.text)
    except Exception:
        pass
    # fallback: always scrape directly when API path is unavailable or returns nothing
    return scrape_rr(url)

def get_pages_from_user():
    """Get a dict of {label: url} from the user.

    Supports:
    - GUI prompt (Tk) when a desktop session is available
    - Terminal prompt fallback

    Input may be comma/space separated tokens. Tokens that look like URLs
    (start with http) are used directly. Otherwise tokens are treated as
    US ZIP codes and a Radioreference browse-by-zip URL is constructed.
    """
    prompt_text = (
        "Enter ZIP codes or Radioreference URLs (comma or space separated).\n"
        "Examples: 60601, 1319, https://www.radioreference.com/db/browse/ctid/606/ham"
    )

    input_str = None
    if gui_session_available():
        try:
            root = tk.Tk()
            # set a friendly title instead of the default 'Tk'
            try:
                root.title('FreqFinder')
            except Exception:
                pass
            # try to set window icon from bundled media image (graceful fallback)
            try:
                img_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'media', 'CashApp_QR.png'))
                icon_img = None
                try:
                    from PIL import Image, ImageTk
                    im = Image.open(img_path)
                    im.thumbnail((64, 64))
                    icon_img = ImageTk.PhotoImage(im)
                except Exception:
                    try:
                        icon_img = tk.PhotoImage(file=img_path)
                    except Exception:
                        icon_img = None
                if icon_img:
                    try:
                        root.iconphoto(False, icon_img)
                        # keep a reference so Tk doesn't garbage-collect it
                        root._icon_img = icon_img
                    except Exception:
                        pass
            except Exception:
                pass
            root.withdraw()
            input_str = simpledialog.askstring("Input", prompt_text)
            root.destroy()
        except Exception:
            input_str = None

    if not input_str:
        try:
            print(prompt_text)
            input_str = input("> ").strip()
        except EOFError:
            print("No input available; exiting.")
            sys.exit(1)

    tokens = [t for t in re.split(r"[,\s]+", input_str) if t]
    pages = {}
    for t in tokens:
        if t.startswith("http://") or t.startswith("https://"):
            label = t
            pages[label] = t
        else:
            # treat as zip code (or simple identifier)
            z = t
            url = f"https://www.radioreference.com/db/browse/zip/{z}/ham"
            pages[f"ZIP {z}"] = url
    return pages


def get_location_from_url(url):
    """Fetch a Radioreference page and try to extract a friendly location name.

    Looks for a top-level H2 (e.g., 'Cook County, Illinois') or the <title> tag
    or breadcrumb items.
    """
    try:
        r = http_get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        h2 = soup.select_one('h2')
        if h2 and h2.text.strip():
            return h2.text.strip()
        # try breadcrumb last item
        bc = soup.select('ol.breadcrumb li')
        if bc:
            last = bc[-1].text.strip()
            if last:
                return last
        # fallback to title
        if soup.title and soup.title.text:
            return soup.title.text.strip()
    except Exception:
        return None
    return None


def get_county_from_zip(zip_code):
    """Given a ZIP code, fetch the RR zip page and try to find the county page link (ctid).

    Returns (label, url) or (None, zip_page_url) on fallback.
    """
    zip_url = f"https://www.radioreference.com/db/browse/zip/{zip_code}/ham"
    try:
        r = http_get(zip_url, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        # look for a link to /db/browse/ctid/\d+
        a = soup.find('a', href=re.compile(r'/db/browse/ctid/\d+'))
        if a and a.get('href'):
            href = a['href']
            label = a.text.strip() or f"County {zip_code}"
            # make absolute URL
            if href.startswith('/'):
                href = 'https://www.radioreference.com' + href
            return (label, href)
    except Exception:
        pass

    # fallback: try to resolve county via zippopotam.us -> reverse geocode -> search RR
    try:
        place = http_get(f'http://api.zippopotam.us/us/{zip_code}', timeout=8).json()
        places = place.get('places', [])
        if places:
            lat = places[0].get('latitude')
            lon = places[0].get('longitude')
            state = places[0].get('state') or place.get('state')
            # reverse geocode with Nominatim to get county
            if lat and lon:
                nom = http_get(
                    f'https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}',
                    headers={'User-Agent': 'chirp-scraper'},
                    timeout=8,
                ).json()
                addr = nom.get('address', {})
                county = addr.get('county')
                state_name = addr.get('state') or state
                if county and state_name:
                    # search RadioReference for county page
                    rr_search = http_get(
                        'https://www.radioreference.com/search/',
                        params={'q': f"{county} {state_name}"},
                        timeout=10,
                    )
                    ssoup = BeautifulSoup(rr_search.text, 'html.parser')
                    a = ssoup.find('a', href=re.compile(r'/db/browse/ctid/\d+'))
                    if a and a.get('href'):
                        href = a['href']
                        if href.startswith('/'):
                            href = 'https://www.radioreference.com' + href
                        label = a.text.strip() or county
                        return (label, href)
    except Exception:
        pass

    # final fallback: return zip page url
    return (None, zip_url)


def get_zip_state(zipcode):
    """Return the U.S. state name for a ZIP code."""
    try:
        r = http_get(f'http://api.zippopotam.us/us/{zipcode}', timeout=8)
        pj = r.json()
        places = pj.get('places', [])
        if not places:
            return None
        return places[0].get('state')
    except Exception:
        return None


def fetch_radio_browser_stations_for_state(state, limit=100):
    """Fetch internet radio station metadata for a U.S. state via Radio Browser."""
    if not state:
        return []
    params = {'countrycode': 'US', 'state': state, 'limit': str(limit)}
    try:
        resp = http_get(f'{RADIO_BROWSER_API_BASE}/stations/search', params=params, timeout=15)
        data = resp.json()
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def get_radio_browser_broadcast_for_zip(zipcode, limit=100):
    """Fetch broadcast station metadata for the ZIP code state using Radio Browser."""
    state = get_zip_state(zipcode)
    if not state:
        return []
    return fetch_radio_browser_stations_for_state(state, limit=limit)


class QRZHelper:
    """QRZ helper stub.

    This class provides the public integration point for QRZ data without
    embedding or shipping QRZ credentials. A full QRZ XML API implementation
    should be added separately and kept private, since QRZ requires a login and
    license agreement.
    """
    def __init__(self, username=None, password=None, api_key=None):
        self.username = username
        self.password = password
        self.api_key = api_key
        self.logged_in = False

    def login(self):
        """Stub login.

        Returns False because QRZ credentials must be provided and the actual
        implementation is not included in this repository.
        """
        self.logged_in = False
        return False

    def lookup_callsign(self, callsign):
        """Return a stub response for a callsign lookup."""
        return {
            'status': 'stub',
            'callsign': callsign,
            'message': 'QRZ helper stub active; implement QRZ XML API access separately with credentials.',
        }

    def lookup_zip(self, zipcode):
        """Return a stub response for a ZIP code lookup."""
        return {
            'status': 'stub',
            'zipcode': zipcode,
            'message': 'QRZ helper stub active; QRZ does not provide a public ZIP-to-frequency feed without a subscription.',
        }


def get_defaults_for_freq(freq):
    """Return pre-loaded defaults for common public-frequency bands if available."""
    try:
        target = float(freq)
    except Exception:
        return {}
    for source in (FRS_GMRS_FREQS, MURS_FREQS, NOAA_FREQS):
        for item in source:
            if len(item) < 2:
                continue
            try:
                source_freq = float(item[1])
            except Exception:
                continue
            if abs(source_freq - target) < 0.001:
                if len(item) >= 4 and isinstance(item[-1], dict):
                    return item[-1]
                return {}
    return {}


def map_zips_to_counties(zips):
    """Map a list of ZIP strings to unique county pages on RadioReference.

    Returns dict {label: url}.
    """
    pages = {}
    seen_urls = set()
    for z in zips:
        lbl, url = get_county_from_zip(z)
        if lbl is None:
            # use zip page as fallback label
            lbl = f'ZIP {z}'
        # dedupe by URL with O(1) lookups
        if url not in seen_urls:
            pages[lbl] = url
            seen_urls.add(url)
    return pages


def launch_gui_and_run(default_pages, output_path):
    import tkinter as tk
    from tkinter import ttk, messagebox
    import webbrowser
    from tkinter import filedialog

    root = tk.Tk()
    # set main window title
    try:
        root.title('FreqFinder')
    except Exception:
        root.title('FreqFinder RR Scraper')

    # try to set window icon from bundled media image (graceful fallback)
    try:
        img_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'media', 'CashApp_QR.png'))
        icon_img = None
        try:
            from PIL import Image, ImageTk
            im = Image.open(img_path)
            im.thumbnail((64, 64))
            icon_img = ImageTk.PhotoImage(im)
        except Exception:
            try:
                icon_img = tk.PhotoImage(file=img_path)
            except Exception:
                icon_img = None
        if icon_img:
            try:
                root.iconphoto(False, icon_img)
                root._icon_img = icon_img
            except Exception:
                pass
    except Exception:
        pass

    menubar = tk.Menu(root)

    # Helper: center a Toplevel on the parent and clamp to screen so buttons stay visible
    def center_and_clamp(win, desired_w, desired_h, parent_win=None):
        try:
            parent = parent_win if parent_win is not None else root
            parent.update_idletasks()
            sw = parent.winfo_screenwidth()
            sh = parent.winfo_screenheight()
            w = min(int(desired_w), max(100, sw - 40))
            h = min(int(desired_h), max(60, sh - 80))
            # try to center on parent
            try:
                px = parent.winfo_x()
                py = parent.winfo_y()
                pw = parent.winfo_width()
                ph = parent.winfo_height()
                x = px + (pw - w) // 2
                y = py + (ph - h) // 2
            except Exception:
                x = (sw - w) // 2
                y = (sh - h) // 2
            # clamp
            x = max(0, min(x, sw - w - 10))
            y = max(0, min(y, sh - h - 10))
            win.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            try:
                win.geometry(f"+0+0")
            except Exception:
                pass
    
    # Variable to store the last exported DataFrame for Save As
    exported_data = {'dataframe': None, 'row_count': 0}
    exporting_flag = {'running': False}
    # Queue for messagebox calls when dialogs are suppressed during export
    _dialog_queue = []
    _messagebox_origs = {}

    def _suppress_messageboxes(enable=True):
        nonlocal _messagebox_origs
        try:
            if enable:
                # save originals
                _messagebox_origs['showinfo'] = messagebox.showinfo
                _messagebox_origs['showwarning'] = messagebox.showwarning
                _messagebox_origs['showerror'] = messagebox.showerror

                def _wrap_info(title, msg=None, **kwargs):
                    if exporting_flag.get('running'):
                        _dialog_queue.append(('info', title, msg))
                    else:
                        _messagebox_origs['showinfo'](title, msg, **kwargs)

                def _wrap_warn(title, msg=None, **kwargs):
                    if exporting_flag.get('running'):
                        _dialog_queue.append(('warn', title, msg))
                    else:
                        _messagebox_origs['showwarning'](title, msg, **kwargs)

                def _wrap_err(title, msg=None, **kwargs):
                    if exporting_flag.get('running'):
                        _dialog_queue.append(('err', title, msg))
                    else:
                        _messagebox_origs['showerror'](title, msg, **kwargs)

                messagebox.showinfo = _wrap_info
                messagebox.showwarning = _wrap_warn
                messagebox.showerror = _wrap_err
            else:
                # restore originals
                if 'showinfo' in _messagebox_origs:
                    messagebox.showinfo = _messagebox_origs.get('showinfo')
                if 'showwarning' in _messagebox_origs:
                    messagebox.showwarning = _messagebox_origs.get('showwarning')
                if 'showerror' in _messagebox_origs:
                    messagebox.showerror = _messagebox_origs.get('showerror')
        except Exception:
            pass

    def _flush_dialog_queue():
        # show queued dialogs now (non-modal) after export completes
        try:
            for typ, title, msg in _dialog_queue:
                try:
                    if typ == 'info':
                        _messagebox_origs.get('showinfo', messagebox.showinfo)(title, msg)
                    elif typ == 'warn':
                        _messagebox_origs.get('showwarning', messagebox.showwarning)(title, msg)
                    else:
                        _messagebox_origs.get('showerror', messagebox.showerror)(title, msg)
                except Exception:
                    pass
            _dialog_queue.clear()
        except Exception:
            pass
    band_checkbuttons = {}
    
    # File menu with Exit and Save As
    filemenu = tk.Menu(menubar, tearoff=0)
    
    def on_save_as():
        if exporting_flag.get('running'):
            messagebox.showwarning('Save As', 'Export in progress — please wait until it completes.')
            return
        if exported_data['dataframe'] is None:
            messagebox.showwarning('Save As', 'No data to save. Please export CSV first.')
            return

        # Create a small progress window and write row-by-row so user sees progress
        progress_window = tk.Toplevel(root)
        progress_window.title('Saving CSV')
        progress_window.resizable(False, False)
        progress_window.transient(root)
        center_and_clamp(progress_window, 400, 120)

        progress_label = tk.Label(progress_window, text='Preparing save...', wraplength=380)
        progress_label.pack(pady=10)
        progress_bar = ttk.Progressbar(progress_window, mode='indeterminate', length=360)
        progress_bar.pack(pady=10, padx=20)
        progress_bar.start()
        progress_status = tk.Label(progress_window, text='', font=('Arial', 9))
        progress_status.pack(pady=5)

        def update_progress(msg):
            progress_status.config(text=msg)
            progress_window.update()

        try:
            # build default filename similar to export: FreqFinder_$Model_Zipcode[#]_$Month
            try:
                from datetime import datetime
                model_raw = None
                try:
                    model_raw = preferences_data.get('selected_model').get()
                except Exception:
                    model_raw = 'Generic'
                model_s = re.sub(r'[^A-Za-z0-9]+', '_', model_raw).strip('_') or 'Model'

                zip_part = 'Export'
                pages_meta = exported_data.get('pages') or {}
                zip_candidates = []
                for k, v in pages_meta.items() if isinstance(pages_meta, dict) else []:
                    m1 = re.search(r"(\d{5})", str(k))
                    m2 = re.search(r"(\d{5})", str(v))
                    if m1:
                        zip_candidates.append(m1.group(1))
                    elif m2:
                        zip_candidates.append(m2.group(1))
                # keep unique zip list in order
                unique_zips = []
                for z in zip_candidates:
                    if z not in unique_zips:
                        unique_zips.append(z)
                if unique_zips:
                    if len(unique_zips) <= 6:
                        zip_part = '-'.join(unique_zips)
                    else:
                        zip_part = f"{unique_zips[0]}[{len(unique_zips)}]"
                else:
                    first_label = next(iter(pages_meta.keys()), 'Export') if isinstance(pages_meta, dict) else 'Export'
                    zip_part = re.sub(r'[^A-Za-z0-9]+', '_', first_label).strip('_')

                month_part = datetime.now().strftime('%b%Y')
                default_name = f"FreqFinder_{model_s}_{zip_part}_{month_part}.csv"
            except Exception:
                default_name = 'chirp_output.csv'

            progress_bar.stop()
            progress_label.config(text='Choose save location...')
            progress_window.update()

            initial_dir = DEFAULT_SAVE_DIR if os.path.isdir(DEFAULT_SAVE_DIR) else None
            save_path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV files','*.csv'),('All files','*.*')], initialdir=initial_dir, initialfile=default_name, title='Save CSV as')
            if not save_path:
                progress_window.destroy()
                return

            # write row-by-row with determinate progress
            outdf = exported_data['dataframe']
            total = exported_data.get('row_count', len(outdf))
            progress_bar.config(mode='determinate', maximum=total, value=0)
            update_progress(f'Writing 0/{total} rows...')
            import csv as _csv
            fieldnames = ['Location'] + list(outdf.columns)
            with open(save_path, 'w', newline='', encoding='utf-8') as wf:
                writer = _csv.DictWriter(wf, fieldnames=fieldnames)
                writer.writeheader()
                i = 0
                out_cols = list(outdf.columns)
                for i, row_tup in enumerate(outdf.itertuples(index=True, name=None), start=1):
                    rec = {'Location': row_tup[0]}
                    for c, v in zip(out_cols, row_tup[1:]):
                        rec[c] = v
                    writer.writerow(rec)
                    progress_bar['value'] = i
                    update_progress(f'Writing {i}/{total} rows...')

            progress_window.destroy()
            messagebox.showinfo('Done', f'Wrote {total} rows to {save_path}')
        except Exception as e:
            progress_window.destroy()
            messagebox.showerror('Error', f'Failed to save CSV: {e}')

    def on_open_file():
        # Open a previously saved CSV and load it into exported_data
        try:
            path = filedialog.askopenfilename(filetypes=[('CSV files','*.csv'),('All files','*.*')], title='Open CSV file')
            if not path:
                return
            try:
                import pandas as _pd
                df = _pd.read_csv(path)
            except Exception:
                # Fallback to csv.DictReader then convert to DataFrame if pandas unavailable
                import csv as _csv
                rows = []
                with open(path, newline='', encoding='utf-8') as rf:
                    reader = _csv.DictReader(rf)
                    for row in reader:
                        rows.append(row)
                try:
                    import pandas as _pd
                    df = _pd.DataFrame(rows)
                except Exception:
                    # Keep as list of dicts if pandas still unavailable
                    exported_data['dataframe'] = rows
                    exported_data['row_count'] = len(rows)
                    exported_data['pages'] = {}
                    messagebox.showinfo('Open File', f'Loaded {len(rows)} rows from {path}')
                    return
            exported_data['dataframe'] = df
            exported_data['row_count'] = len(df)
            exported_data['pages'] = {}
            messagebox.showinfo('Open File', f'Loaded {len(df)} rows from {path}')
        except Exception as e:
            messagebox.showerror('Open File', f'Failed to open file: {e}')
    
    filemenu.add_command(label='Open File...', command=lambda: on_open_file())
    filemenu.add_command(label='Save As...', command=on_save_as)
    filemenu.add_separator()
    
    def on_exit():
        try:
            root.destroy()
        except Exception:
            sys.exit(0)
    filemenu.add_command(label='Exit', command=on_exit)
    # Themes submenu (10 popular themes)
    THEMES = {
        'Light': {'bg': '#ffffff', 'fg': '#000000', 'btn_bg': '#e0e0e0'},
        'Dark': {'bg': '#2e3440', 'fg': '#d8dee9', 'btn_bg': '#4c566a'},
        'Solarized Light': {'bg': '#fdf6e3', 'fg': '#586e75', 'btn_bg': '#eee8d5'},
        'Solarized Dark': {'bg': '#002b36', 'fg': '#839496', 'btn_bg': '#073642'},
        'Gruvbox': {'bg': '#fbf1c7', 'fg': '#3c3836', 'btn_bg': '#ebdbb2'},
        'Monokai': {'bg': '#272822', 'fg': '#f8f8f2', 'btn_bg': '#75715e'},
        'Nord': {'bg': '#2e3440', 'fg': '#d8dee9', 'btn_bg': '#3b4252'},
        'Dracula': {'bg': '#282a36', 'fg': '#f8f8f2', 'btn_bg': '#44475a'},
        'High Contrast': {'bg': '#000000', 'fg': '#ffffff', 'btn_bg': '#ffcc00'},
        'Classic': {'bg': root.cget('bg') if hasattr(root, 'cget') else '#f0f0f0', 'fg': '#000000', 'btn_bg': '#d9d9d9'},
    }

    def apply_theme(name):
        cfg = THEMES.get(name)
        if not cfg:
            return
        try:
            root.configure(bg=cfg.get('bg', ''))
            # Global option assignments for Tk widgets
            root.option_add('*Background', cfg.get('bg', ''))
            root.option_add('*Foreground', cfg.get('fg', ''))
            root.option_add('*Button.Background', cfg.get('btn_bg', ''))
            root.option_add('*Button.activeBackground', cfg.get('btn_bg', ''))
            root.option_add('*Button.Foreground', cfg.get('fg', ''))
            root.option_add('*Entry.Background', cfg.get('bg', ''))
            root.option_add('*Entry.Foreground', cfg.get('fg', ''))
            root.option_add('*Label.Background', cfg.get('bg', ''))
            root.option_add('*Label.Foreground', cfg.get('fg', ''))
            root.option_add('*Checkbutton.Background', cfg.get('bg', ''))
            root.option_add('*Checkbutton.Foreground', cfg.get('fg', ''))
            root.option_add('*Checkbutton.ActiveBackground', cfg.get('btn_bg', ''))
            root.option_add('*Checkbutton.SelectColor', cfg.get('btn_bg', ''))
            root.option_add('*Listbox.Background', cfg.get('bg', ''))
            root.option_add('*Listbox.Foreground', cfg.get('fg', ''))
            root.option_add('*Listbox.SelectBackground', cfg.get('btn_bg', ''))
            root.option_add('*Listbox.SelectForeground', cfg.get('fg', ''))
            root.option_add('*Menu.Background', cfg.get('bg', ''))
            root.option_add('*Menu.Foreground', cfg.get('fg', ''))

            # Attempt to recolor existing widgets immediately
            def _recolor(w):
                try:
                    w.configure(bg=cfg.get('bg', ''), fg=cfg.get('fg', ''))
                except Exception:
                    pass
                try:
                    w.configure(activebackground=cfg.get('btn_bg', ''))
                except Exception:
                    pass
                for c in w.winfo_children():
                    _recolor(c)
            _recolor(root)
        except Exception:
            pass

    themesmenu = tk.Menu(filemenu, tearoff=0)
    for tname in list(THEMES.keys()):
        themesmenu.add_command(label=tname, command=lambda n=tname: apply_theme(n))
    filemenu.add_cascade(label='Themes', menu=themesmenu)
    menubar.add_cascade(label='File', menu=filemenu)
    helpmenu = tk.Menu(menubar, tearoff=0)
    
    # Getting Started / Quick Guide
    def show_getting_started():
        guide_window = tk.Toplevel(root)
        guide_window.title('Getting Started with FreqFinder')
        center_and_clamp(guide_window, 700, 650)
        guide_window.resizable(True, True)
        
        # Create scrollable frame
        canvas = tk.Canvas(guide_window)
        scrollbar = ttk.Scrollbar(guide_window, orient='vertical', command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)
        
        scrollable_frame.bind(
            '<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all'))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Guide content
        sections = [
            ('📍 Enter Location', 
             'Enter a 5-digit ZIP code or RadioReference URL\nto search for frequencies in that area.\nYou can enter up to 4 locations.'),
            ('📡 Select Bands',
             'Choose which frequency bands to include:\n• 70cm: 420-450 MHz\n• 2m: 144-148 MHz\n• NOAA: Weather alerts\n• MURS: License-free\n• FRS/GMRS: Family radio service'),
            ('🎚️ Order Bands',
             'Use Up/Down buttons to prioritize bands.\nFirst band appears first in your export.'),
            ('⚙️ Set Preferences',
             'Go to Preferences > Radio & Export Settings to:\n• Select your radio model\n• Choose export quality level\n• See supported features'),
            ('💾 Export',
             'Click Export CSV to create your CHIRP file.\nChoose where to save the exported file.'),
            ('💾 Save As',
             'After exporting, use File > Save As to save\nthe same data to another location.'),
            ('🔧 Quality Levels',
             '• Default: Essential features\n• Standard: Extended features + deduplication\n• Advanced: Power user features\n• High Quality: Maximum optimization'),
            ('📱 Radio Models',
             'FreqFinder supports:\n• Generic (all CHIRP radios)\n• Baofeng UV-5R/UV-82\n• Motorola (Professional)\n• Kenwood (VHF/UHF)'),
            ('💡 Tips',
             '• Hover over elements for helpful tips\n• RadioReference has the most complete data\n• Check Help > RadioReference for frequency info\n• Contact GitHub for support/issues'),
        ]
        
        for title, content in sections:
            # Section title
            title_label = tk.Label(scrollable_frame, text=title, font=('Arial', 11, 'bold'), justify='left')
            title_label.pack(anchor='w', padx=15, pady=(10, 5))
            
            # Section content
            content_label = tk.Label(scrollable_frame, text=content, font=('Arial', 9), 
                                    justify='left', wraplength=650, fg='#333333')
            content_label.pack(anchor='w', padx=15, pady=(0, 10))
        
        # Bottom instruction
        bottom_label = tk.Label(scrollable_frame, text='Hover over any button or field for quick help!', 
                              font=('Arial', 9, 'italic'), foreground='#0066cc', pady=15)
        bottom_label.pack()
        
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
    
    helpmenu.add_command(label='Getting Started', command=show_getting_started)
    helpmenu.add_separator()
    # Link to RadioReference site
    def open_radioreference():
        try:
            webbrowser.open('https://www.radioreference.com')
        except Exception:
            pass
    helpmenu.add_command(label='RadioReference', command=open_radioreference)
    # How-To opens the project README
    def open_readme():
        try:
            from pathlib import Path
            readme = os.path.abspath(os.path.join(os.path.dirname(__file__), 'README.md'))
            webbrowser.open(Path(readme).as_uri())
        except Exception:
            try:
                pass
                # webbrowser.open('https://github.com/Drizztdowhateva/Chirp_Scrape')  # preserved upstream reference for attribution
            except Exception:
                pass
    helpmenu.add_command(label='How-To', command=open_readme)

    # Contact submenu
    contactmenu = tk.Menu(helpmenu, tearoff=0)

    def open_donations():
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'media', 'index.html'))
        try:
            from pathlib import Path
            webbrowser.open(Path(html_path).as_uri())
        except Exception:
            webbrowser.open(f'file://{html_path}')

    def open_github():
        try:
            webbrowser.open('https://github.com/Drizztdowhateva/Chirp_Scrape')  # preserved upstream reference for attribution
        except Exception:
            pass

    contactmenu.add_command(label='Donations', command=open_donations)
    contactmenu.add_command(label='GitHub Project', command=open_github)
    helpmenu.add_cascade(label='Contact', menu=contactmenu)

    # Improvements submenu — extra options and suggestions for power users
    improvemenu = tk.Menu(helpmenu, tearoff=0)

    def show_improvement_options():
        """Show a dialog listing suggested improvements and next-step options."""
        dlg = tk.Toplevel(root)
        dlg.title('Suggested Improvements & Extra Options')
        dlg.resizable(True, True)
        center_and_clamp(dlg, 750, 580)

        canvas = tk.Canvas(dlg)
        scrollbar = ttk.Scrollbar(dlg, orient='vertical', command=canvas.yview)
        sf = tk.Frame(canvas)
        sf.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=sf, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        tk.Label(sf, text='💡 Suggested Improvements & Extra Options',
                 font=('Arial', 12, 'bold')).pack(anchor='w', padx=15, pady=(12, 6))

        improvements = [
            ('📦 Batch ZIP Processing',
             'Import a list of ZIP codes from a text file and export one combined CSV — useful for'
             ' building channel lists that span multiple counties or regions.'),
            ('📤 Multiple Export Formats',
             'Export to additional formats beyond CHIRP CSV: Kenwood MCP, Icom CS, RT Systems,'
             ' or plain-text frequency lists that can be pasted into other programming software.'),
            ('🔍 Frequency Deduplication',
             'Detect and merge duplicate frequencies that appear across multiple RadioReference'
             ' pages, keeping the entry with the most metadata (tone, name, description).'),
            ('⏱ Scheduled Refresh',
             'Optionally re-fetch RadioReference pages on a configurable schedule so your'
             ' channel list stays up-to-date without manual intervention.'),
            ('🌐 Offline / Cached Mode',
             'Cache the last successful scrape result per URL so the app can be used offline,'
             ' falling back to cached data when RadioReference is unreachable.'),
            ('📊 Frequency Statistics',
             'Show a summary panel after export: number of channels per band, tone distribution,'
             ' and most-common repeater offsets — helpful for spotting data-quality issues.'),
            ('🔒 GMRS License Checker',
             'Optional reminder that GMRS operation requires an FCC license; add a gentle'
             ' warning when exporting GMRS channels without a stored license number.'),
            ('🛰 P25 / DMR Channel Tagging',
             'Auto-detect P25 and DMR systems from RadioReference tags and annotate exported'
             ' channels so they can be filtered or highlighted in a compatible radio.'),
            ('📝 Notes & Labels',
             'Allow the user to attach free-text notes to individual channels before exporting,'
             ' stored in the CHIRP Comment field.'),
            ('🎨 Theme Customization',
             'Expose all theme colors in the Preferences dialog so users can fully'
             ' personalize the UI appearance without editing source code.'),
        ]

        for title_text, desc in improvements:
            tk.Label(sf, text=title_text, font=('Arial', 10, 'bold'),
                     justify='left').pack(anchor='w', padx=15, pady=(8, 2))
            tk.Label(sf, text=desc, font=('Arial', 9), justify='left',
                     wraplength=700, fg='#444444').pack(anchor='w', padx=30, pady=(0, 6))

        tk.Label(sf, text='👉 Have an idea? Open an issue on GitHub!',
                 font=('Arial', 9, 'italic'), fg='#0066cc').pack(anchor='w', padx=15, pady=(10, 6))

        def _open_issues():
            webbrowser.open('https://github.com/Drizztdowhateva/Chirp_Scrape/issues')
        tk.Button(sf, text='Open GitHub Issues', command=_open_issues,
                  bg='#0066cc', fg='white', font=('Arial', 9, 'bold')).pack(anchor='w', padx=15, pady=(0, 15))

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

    improvemenu.add_command(label='Suggested Improvements…', command=show_improvement_options)
    helpmenu.add_cascade(label='Improvements', menu=improvemenu)

    # Firmware submenu
    firmwaremenu = tk.Menu(helpmenu, tearoff=0)
    
    def open_baofeng_unlock():
        webbrowser.open('https://www.miklor.com/COM/UV5R_Unlock.php')
    
    def open_onesdr_unlock():
        webbrowser.open('https://www.onesdr.com/how-to-unlock-a-baofeng-uv-5r/')
    
    def open_baofeng_unlock_guide():
        webbrowser.open('https://www.miklor.com/COM/UV5R.php')
    
    def open_chirp_firmware():
        webbrowser.open('https://chirp.danplanet.com/')

    # John Miklor (WA9QJV) — author of the definitive CHIRP programming guides at miklor.com
    def open_miklor_chirp_guide():
        webbrowser.open('https://www.miklor.com/CHIRP/index.php')

    # CHIRP open-source project on GitHub
    # Repo owner: Dan Smith (KK7DS) — github.com/kk7ds/chirp
    # Lead developer/maintainer: Jim Unroe (KC9HI)
    def open_chirp_github():
        webbrowser.open('https://github.com/kk7ds/chirp')
    
    def open_firmware_resources():
        resources_window = tk.Toplevel(root)
        resources_window.title('Firmware Unlock Resources')
        resources_window.resizable(True, True)
        center_and_clamp(resources_window, 700, 500)
        
        # Create scrollable frame
        canvas = tk.Canvas(resources_window)
        scrollbar = ttk.Scrollbar(resources_window, orient='vertical', command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)
        
        scrollable_frame.bind(
            '<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all'))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Content
        title = tk.Label(scrollable_frame, text='Firmware Unlock & Upgrade Resources', 
                        font=('Arial', 12, 'bold'), justify='left')
        title.pack(anchor='w', padx=15, pady=(10, 15))
        
        resources = [
            ('Unlock Firmware — Baofeng UV-5R (Miklor)', 'Miklor.com - Firmware unlock steps and notes; unlocks firmware allowing programming of FRS/GMRS channels', 
             open_baofeng_unlock),
            ('Unlock Firmware — Baofeng UV-5R (OneSDR)', 'OneSDR - How to unlock a Baofeng UV-5R (steps and notes); firmware unlock to enable GMRS/FRS programming',
             open_onesdr_unlock),
            ('Baofeng Full Guide', 'Miklor.com - Full UV-5R technical documentation and tricks',
             open_baofeng_unlock_guide),
            ('CHIRP Firmware', 'CHIRP official firmware database and radio programming tool',
             open_chirp_firmware),
            ('CHIRP Programming Guides (John Miklor, WA9QJV)',
             'Miklor.com — Comprehensive CHIRP radio programming tutorials and channel guides by John Miklor (WA9QJV)',
             open_miklor_chirp_guide),
            ('CHIRP GitHub (Dan Smith KK7DS / Jim Unroe KC9HI)',
             'Official CHIRP open-source project on GitHub — repo owner: Dan Smith (KK7DS),'
             ' lead developer: Jim Unroe (KC9HI). Report bugs, browse source, download releases.',
             open_chirp_github),
        ]
        
        for title_text, desc, cmd in resources:
            btn = tk.Button(scrollable_frame, text=title_text, command=cmd, 
                           bg='#0066cc', fg='white', width=40, font=('Arial', 10, 'bold'))
            btn.pack(anchor='w', padx=15, pady=(5, 2))
            
            desc_label = tk.Label(scrollable_frame, text=desc, font=('Arial', 9), 
                                 justify='left', wraplength=650, fg='#666666')
            desc_label.pack(anchor='w', padx=35, pady=(0, 12))
        
        info_frame = tk.Frame(scrollable_frame, bg='#f0f0f0', relief='solid', borderwidth=1)
        info_frame.pack(fill='x', padx=15, pady=(15, 0))
        
        info_text = tk.Label(info_frame, text='⚠️ Warning: Unlocking firmware may void warranty. Always backup before modifications.',
                            font=('Arial', 9), fg='#cc0000', bg='#f0f0f0', justify='left', wraplength=650)
        info_text.pack(padx=10, pady=10)
        
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
    
    firmwaremenu.add_command(label='Firmware Unlock Guide', command=open_firmware_resources)
    firmwaremenu.add_separator()
    firmwaremenu.add_command(label='Unlock Firmware — Baofeng UV-5R (Miklor)', command=open_baofeng_unlock)
    firmwaremenu.add_command(label='Unlock Firmware — Baofeng UV-5R (OneSDR)', command=open_onesdr_unlock)
    firmwaremenu.add_command(label='Baofeng Full Guide (Miklor)', command=open_baofeng_unlock_guide)
    firmwaremenu.add_separator()
    firmwaremenu.add_command(label='CHIRP Firmware Database', command=open_chirp_firmware)
    firmwaremenu.add_command(label='CHIRP Programming Guides (John Miklor)', command=open_miklor_chirp_guide)
    firmwaremenu.add_command(label='CHIRP GitHub (Dan Smith KK7DS)', command=open_chirp_github)
    helpmenu.add_cascade(label='Firmware', menu=firmwaremenu)

    # Videos submenu — John Miklor (WA9QJV) video tutorials
    videosmenu = tk.Menu(helpmenu, tearoff=0)

    def open_miklor_youtube():
        webbrowser.open('https://www.youtube.com/@wa9qjv')

    def open_miklor_chirp_videos():
        webbrowser.open('https://www.miklor.com/CHIRP/index.php')

    def open_miklor_baofeng_videos():
        webbrowser.open('https://www.miklor.com/uv5r/')

    videosmenu.add_command(label='John Miklor (WA9QJV) — YouTube Channel', command=open_miklor_youtube)
    videosmenu.add_separator()
    videosmenu.add_command(label='CHIRP Programming Videos (Miklor)', command=open_miklor_chirp_videos)
    videosmenu.add_command(label='Baofeng UV-5R Videos (Miklor)', command=open_miklor_baofeng_videos)
    helpmenu.add_cascade(label='Videos', menu=videosmenu)

    # Chirp submenu — CHIRP project references (Dan Smith KK7DS / Jim Unroe KC9HI)
    chirpmenu = tk.Menu(helpmenu, tearoff=0)

    def open_chirp_site():
        webbrowser.open('https://chirp.danplanet.com/')

    def open_chirp_project_github():
        webbrowser.open('https://github.com/kk7ds/chirp')

    def open_chirp_downloads():
        webbrowser.open('https://chirp.danplanet.com/projects/chirp/wiki/Download')

    def open_chirp_daily_builds():
        webbrowser.open('https://chirp.danplanet.com/projects/chirp/wiki/Download#Daily-images')

    def open_chirp_getting_started():
        webbrowser.open('https://chirp.danplanet.com/projects/chirp/wiki/GettingStarted')

    def open_chirp_wiki():
        webbrowser.open('https://chirp.danplanet.com/projects/chirp/wiki/Home')

    def open_chirp_contributors():
        webbrowser.open('https://github.com/kk7ds/chirp/graphs/contributors')

    def open_qrz_diagnostics():
        dlg = tk.Toplevel(root)
        dlg.title('QRZ Diagnostics')
        dlg.resizable(True, True)
        center_and_clamp(dlg, 600, 360)

        txt = tk.Text(dlg, wrap='word', bg='#f5f5f5')
        txt.pack(fill='both', expand=True, padx=10, pady=10)
        txt.insert('end', 'QRZ Diagnostics\n')
        txt.insert('end', '===================\n')
        txt.insert('end', 'QRZ helper stub class is available.\n')
        has_key = bool(os.environ.get('RR_API_KEY') or os.environ.get('RR_API_PASS'))
        txt.insert('end', f'QRZ credentials environment present: {has_key}\n')
        txt.insert('end', 'QRZ XML API access is not implemented in this stub.\n')
        txt.insert('end', 'Use `RR_API_KEY` or `RR_API_PASS` only if you add private QRZ integration separately.\n')
        txt.config(state='disabled')

    def open_diagnostics():
        dlg = tk.Toplevel(root)
        dlg.title('Diagnostics')
        dlg.resizable(True, True)
        center_and_clamp(dlg, 600, 380)

        txt = tk.Text(dlg, wrap='word', bg='#f5f5f5')
        txt.pack(fill='both', expand=True, padx=10, pady=10)
        source_name = preferences_data.get('selected_source').get() if preferences_data.get('selected_source') else 'RadioReference'
        txt.insert('end', 'Diagnostics\n')
        txt.insert('end', '===========\n')
        txt.insert('end', f'Selected source: {source_name}\n')
        txt.insert('end', f'RadioReference index loaded: {bool(rr_index)} (radioref.csv)\n')
        txt.insert('end', f'Radio Browser API base: {RADIO_BROWSER_API_BASE}\n')
        txt.insert('end', f'QRZ helper stub available: yes\n')
        txt.insert('end', f'QRZ credentials environment present: {bool(os.environ.get("RR_API_KEY") or os.environ.get("RR_API_PASS"))}\n')
        txt.insert('end', '\nUse the Preferences menu to change the selected source.\n')
        txt.config(state='disabled')

    def open_joe_ungor_github():
        webbrowser.open('https://github.com/search?q=Joe+Ungor+CHIRP&type=users')

    chirpmenu.add_command(label='CHIRP Website (Dan Smith KK7DS)', command=open_chirp_site)
    chirpmenu.add_command(label='CHIRP GitHub (Dan Smith KK7DS / Jim Unroe KC9HI)', command=open_chirp_project_github)
    chirpmenu.add_separator()
    helpmenu.add_command(label='Diagnostics', command=open_diagnostics)
    helpmenu.add_separator()
    chirpmenu.add_command(label='CHIRP Downloads', command=open_chirp_downloads)
    chirpmenu.add_command(label='CHIRP Daily Builds', command=open_chirp_daily_builds)
    chirpmenu.add_command(label='CHIRP Getting Started Guide', command=open_chirp_getting_started)
    helpmenu.add_cascade(label='CHIRP', menu=chirpmenu)

    # Refrences submenu (intentional spelling per menu request)
    refrencesmenu = tk.Menu(helpmenu, tearoff=0)
    refrencesmenu.add_command(label='John Miklor CHIRP Guide (WA9QJV)', command=open_miklor_chirp_guide)
    refrencesmenu.add_command(label='Joe Ungor GitHub (Search)', command=open_joe_ungor_github)
    refrencesmenu.add_command(label='CHIRP GitHub (Dan Smith KK7DS / Jim Unroe KC9HI)', command=open_chirp_project_github)
    refrencesmenu.add_command(label='CHIRP Contributors on GitHub', command=open_chirp_contributors)
    refrencesmenu.add_separator()
    refrencesmenu.add_command(label='John Miklor YouTube Channel (WA9QJV)', command=open_miklor_youtube)
    refrencesmenu.add_command(label='John Miklor CHIRP Videos', command=open_miklor_chirp_videos)
    refrencesmenu.add_command(label='John Miklor Baofeng Videos', command=open_miklor_baofeng_videos)
    refrencesmenu.add_separator()
    refrencesmenu.add_command(label='CHIRP Wiki / Documentation', command=open_chirp_wiki)
    refrencesmenu.add_command(label='CHIRP Downloads', command=open_chirp_downloads)
    refrencesmenu.add_command(label='CHIRP Program Website', command=open_chirp_site)
    helpmenu.add_cascade(label='Refrences', menu=refrencesmenu)
    
    # SOAP Debug submenu
    def open_soap_debug():
        dlg = tk.Toplevel(root)
        dlg.title('SOAP Debug')
        dlg.resizable(True, True)
        center_and_clamp(dlg, 800, 500)
        frm = tk.Frame(dlg)
        frm.pack(fill='both', expand=True)
        left = tk.Frame(frm)
        left.pack(side='left', fill='y')
        right = tk.Frame(frm)
        right.pack(side='right', fill='both', expand=True)

        ops_list = tk.Listbox(left, width=40)
        ops_list.pack(fill='y', expand=True)
        details = tk.Text(right)
        details.pack(fill='both', expand=True)

        from rr_api import inspect_wsdl, call_soap_method
        try:
            ops = inspect_wsdl()
        except Exception as e:
            details.insert('end', f'Failed to inspect WSDL: {e}')
            return

        for k in sorted(ops.keys()):
            ops_list.insert('end', k)

        def on_select(evt=None):
            sel = ops_list.curselection()
            if not sel:
                return
            name = ops_list.get(sel[0])
            info = ops.get(name, {})
            details.delete('1.0', 'end')
            details.insert('end', f"Operation: {name}\n")
            details.insert('end', f"Input: {info.get('input')}\n")
            details.insert('end', f"Output: {info.get('output')}\n")
            details.insert('end', f"Doc: {info.get('doc')}\n")
            details.insert('end', '\nParameters JSON (optional) then press Call:\n')
            details.insert('end', '{\n  \n}')

        ops_list.bind('<<ListboxSelect>>', on_select)

        def call_op():
            sel = ops_list.curselection()
            if not sel:
                return
            name = ops_list.get(sel[0])
            txt = details.get('1.0', 'end')
            # assume JSON params at end after marker
            try:
                jstart = txt.rfind('{')
                if jstart != -1:
                    params = json.loads(txt[jstart:])
                else:
                    params = {}
            except Exception as e:
                details.insert('end', f'\nFailed to parse JSON params: {e}')
                return
            try:
                key = os.environ.get('RR_API_PASS') or os.environ.get('RR_API_KEY') or RR_API_KEY
                if not key:
                    details.insert('end', '\nNo API key available; load/encrypt one first')
                    return
                resp = call_soap_method(key, name, **params)
                try:
                    import json as _json
                    details.insert('end', '\nResponse:\n')
                    details.insert('end', _json.dumps(resp, default=lambda o: getattr(o, '__dict__', str(o)), indent=2))
                except Exception:
                    details.insert('end', f'\n{resp}')
            except Exception as e:
                details.insert('end', f'\nCall failed: {e}')

        btn_frame = tk.Frame(dlg)
        btn_frame.pack(fill='x')
        tk.Button(btn_frame, text='Call', command=call_op).pack(side='left', padx=8, pady=6)

    # SOAP Debug removed from Help menu per request

    # --- API key selection dropdown ---
    try:
        import rr_api
    except Exception:
        rr_api = None

    

    def ensure_enc_path():
        return os.path.abspath(os.path.join(os.path.dirname(__file__), 'rr_api.enc'))

    def handle_api_choice(selection):
        nonlocal rr_api
        global RR_API_KEY
        enc_path = ensure_enc_path()
        if selection == 'Enter API key...':
            # Prompt user to enter API key and passphrase, then encrypt to file
            try:
                api = simpledialog.askstring('API Key', 'Enter RadioReference API Key (will be encrypted)')
            except Exception:
                api = None
            if not api:
                return
            try:
                p = simpledialog.askstring('Passphrase', 'Enter passphrase to encrypt key', show='*')
            except Exception:
                p = None
            if not p:
                messagebox.showwarning('API', 'No passphrase provided; aborted')
                return
            try:
                if rr_api is None:
                    import rr_api as rr_api
                rr_api.encrypt_api_key(api, p, outpath=enc_path)
                os.environ['RR_API_PASS'] = p
                RR_API_KEY = api
                if 'api_status' in globals().get('preferences_data', {}):
                    preferences_data['api_status'].set('Loaded')
                messagebox.showinfo('API', 'Encrypted API key saved')
            except Exception as e:
                messagebox.showerror('API', f'Encryption failed: {e}')
        elif selection == 'Use built-in (encrypted)':
            # Encrypt the provided hardcoded key and store a passphrase in a local dotfile
            builtin = 'fcb8749c-f4c9-11f0-bb32-0ef97433b5f9'
            passfile = os.path.abspath(os.path.join(os.path.dirname(__file__), '.rr_api_pass'))
            try:
                # generate random passphrase and save it to dotfile with restricted perms
                import secrets
                p = secrets.token_urlsafe(24)
                if rr_api is None:
                    import rr_api as rr_api
                rr_api.encrypt_api_key(builtin, p, outpath=enc_path)
                try:
                    with open(passfile, 'w', encoding='utf-8') as pf:
                        pf.write(p)
                    os.chmod(passfile, 0o600)
                except Exception:
                    # best-effort store
                    pass
                os.environ['RR_API_PASS'] = p
                RR_API_KEY = builtin
                if 'api_status' in globals().get('preferences_data', {}):
                    preferences_data['api_status'].set('Loaded')
                messagebox.showinfo('API', f'Built-in key encrypted and saved to {enc_path}')
            except Exception as e:
                messagebox.showerror('API', f'Failed to encrypt built-in key: {e}')
        else:
            messagebox.showwarning('API', f'Unknown API action: {selection}')

    # Add API menu to the menubar (commands mirror previous dropdown)
    apimenu = tk.Menu(menubar, tearoff=0)
    apimenu.add_command(label='Enter API key...', command=lambda: handle_api_choice('Enter API key...'))
    apimenu.add_command(label='Use built-in (encrypted)', command=lambda: handle_api_choice('Use built-in (encrypted)'))
    apimenu.add_separator()
    apimenu.add_command(label='QRZ Diagnostics', command=open_qrz_diagnostics)
    menubar.add_cascade(label='API', menu=apimenu)

    # Preferences Menu with Model Selection and Customization
    persistent_settings = load_persistent_settings()
    for key, default in DEFAULT_PERSISTENT_SETTINGS.items():
        if key not in persistent_settings:
            persistent_settings[key] = default

    preferences_data = {
        'selected_model': tk.StringVar(value=persistent_settings.get('selected_model', 'Generic')),
        'selected_source': tk.StringVar(value=persistent_settings.get('selected_source', 'RadioReference')),
        'customization_level': tk.StringVar(value=persistent_settings.get('customization_level', 'Default')),
        'api_status': tk.StringVar(value='Loaded' if RR_API_KEY else 'Not loaded'),
        'model_features': {},
        'frs_gmrs_unlock': tk.IntVar(value=int(persistent_settings.get('frs_gmrs_unlock', 0)) if persistent_settings.get('frs_gmrs_unlock') is not None else 0),
        'scanner_mode': tk.IntVar(value=int(persistent_settings.get('scanner_mode', 0)) if persistent_settings.get('scanner_mode') is not None else 0),
    }
    
    def open_preferences():
        pref_window = tk.Toplevel(root)
        pref_window.title('Preferences')
        # clamp minimums to screen size
        try:
            sw = root.winfo_screenwidth()
            sh = root.winfo_screenheight()
            pref_window.minsize(min(700, max(200, sw-40)), min(600, max(120, sh-80)))
        except Exception:
            pref_window.minsize(700, 600)
        pref_window.grab_set()
        center_and_clamp(pref_window, 750, 650)
        
        # Title
        title_frame = tk.Frame(pref_window)
        title_frame.pack(fill='x', padx=15, pady=(15, 10))
        tk.Label(title_frame, text='Application Preferences', font=('Arial', 14, 'bold')).pack()
        
        # Create notebook (tabbed interface)
        notebook = ttk.Notebook(pref_window)
        notebook.pack(fill='both', expand=True, padx=15, pady=(10, 15))
        
        # ===== TAB 1: RADIO MODELS =====
        radio_frame = ttk.Frame(notebook)
        notebook.add(radio_frame, text='📻 Radio Models')
        
        # Create scrollable content for radio frame
        radio_canvas = tk.Canvas(radio_frame)
        radio_scrollbar = ttk.Scrollbar(radio_frame, orient='vertical', command=radio_canvas.yview)
        radio_scrollable_frame = tk.Frame(radio_canvas)
        
        radio_scrollable_frame.bind(
            '<Configure>',
            lambda e: radio_canvas.configure(scrollregion=radio_canvas.bbox('all'))
        )
        
        radio_canvas.create_window((0, 0), window=radio_scrollable_frame, anchor='nw')
        radio_canvas.configure(yscrollcommand=radio_scrollbar.set)
        
        tk.Label(radio_scrollable_frame, text='Select Your Radio Model:', font=('Arial', 10, 'bold')).pack(anchor='w', padx=10, pady=(10, 5))
        model_var = tk.StringVar(value=preferences_data['selected_model'].get())
        
        model_combo = ttk.Combobox(radio_scrollable_frame, textvariable=model_var, state='readonly', width=40)
        model_combo['values'] = [RADIO_MODELS[m]['name'] for m in RADIO_MODELS.keys()]
        model_combo.pack(fill='x', padx=10, pady=(5, 10))

        tk.Label(radio_scrollable_frame, text='Data Source:', font=('Arial', 10, 'bold')).pack(anchor='w', padx=10, pady=(10, 5))
        source_var = tk.StringVar(value=preferences_data['selected_source'].get())
        source_combo = ttk.Combobox(radio_scrollable_frame, textvariable=source_var, state='readonly', width=40)
        source_combo['values'] = ['RadioReference', 'Radio Browser']
        source_combo.pack(fill='x', padx=10, pady=(5, 10))
        source_desc_var = tk.StringVar(value='Choose RadioReference for repeater frequencies, or Radio Browser for public broadcast station metadata.')
        source_desc_label = tk.Label(radio_scrollable_frame, textvariable=source_desc_var, wraplength=700, justify='left', foreground='#666666', font=('Arial', 9))
        source_desc_label.pack(anchor='w', padx=10, pady=(0, 15))

        scanner_mode_var = preferences_data.get('scanner_mode') if preferences_data.get('scanner_mode') else tk.IntVar(value=0)
        scanner_mode_cb = tk.Checkbutton(radio_scrollable_frame, text='Scanner mode (include WX but mark skipped)', variable=scanner_mode_var)
        scanner_mode_cb.pack(anchor='w', padx=10, pady=(0, 12))
        ToolTip(scanner_mode_cb, 'When enabled, NOAA/WX channels are still exported but marked as skipped so scanner mode passes over them.')

        # Model description
        model_desc_var = tk.StringVar(value=RADIO_MODELS['Generic']['description'])
        desc_label = tk.Label(radio_scrollable_frame, textvariable=model_desc_var, wraplength=700, justify='left', foreground='#666666', font=('Arial', 9))
        desc_label.pack(anchor='w', padx=10, pady=(0, 15))

        # Option: Treat FRS/GMRS as unlocked (enable bandplan/programming on unlocked radios)
        frs_pref_var = preferences_data.get('frs_gmrs_unlock') if preferences_data.get('frs_gmrs_unlock') else tk.IntVar(value=0)
        frs_pref_cb = tk.Checkbutton(radio_scrollable_frame, text='Treat FRS/GMRS as unlocked (enable bandplan/programming)', variable=frs_pref_var)
        frs_pref_cb.pack(anchor='w', padx=10, pady=(6, 12))
        ToolTip(frs_pref_cb, 'Check if your Baofeng is firmware-unlocked to allow programming FRS/GMRS channels')
        
        # Model features display
        tk.Label(radio_scrollable_frame, text='Supported Features:', font=('Arial', 9, 'bold')).pack(anchor='w', padx=10, pady=(5, 5))
        
        features_text = tk.Text(radio_scrollable_frame, height=10, width=85, state='disabled', bg='#f5f5f5', relief='solid', padx=8, pady=6)
        features_text.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        def update_model_display(*args):
            selected_name = model_var.get()
            selected_key = None
            for key, model in RADIO_MODELS.items():
                if model['name'] == selected_name:
                    selected_key = key
                    break
            if selected_key:
                model_desc_var.set(RADIO_MODELS[selected_key]['description'])
                preferences_data['model_features'] = RADIO_MODELS[selected_key]
                
                # Update features display
                features_text.config(state='normal')
                features_text.delete('1.0', 'end')
                model_info = RADIO_MODELS[selected_key]
                features = []
                if model_info.get('supports_tone'):
                    features.append('✓ CTCSS Tones')
                if model_info.get('supports_dtcs'):
                    features.append('✓ DTCS Codes')
                if model_info.get('supports_duplex'):
                    features.append('✓ Duplex (+/-)')
                if model_info.get('supports_offset'):
                    features.append('✓ Offset')
                if model_info.get('supports_color_code'):
                    features.append('✓ DMR Color Code')
                if model_info.get('supports_timeslot'):
                    features.append('✓ DMR Timeslot')
                if model_info.get('supports_digital_mode'):
                    features.append('✓ Digital Mode')
                if model_info.get('supports_skip'):
                    features.append('✓ Skip Flag')
                if model_info.get('supports_mode'):
                    features.append('✓ Mode Selection')
                if model_info.get('supports_step'):
                    features.append('✓ Step Sizes')
                features.append(f'\n📊 Max Channels: {model_info.get("max_channels", "N/A")}')
                features_text.insert('end', '\n'.join(features))
                features_text.config(state='disabled')
        
        model_combo.bind('<<ComboboxSelected>>', update_model_display)
        update_model_display()  # Initial display
        
        radio_canvas.pack(side='left', fill='both', expand=True)
        radio_scrollbar.pack(side='right', fill='y')
        
        # ===== TAB 2: EXPORT QUALITY =====
        export_frame = ttk.Frame(notebook)
        notebook.add(export_frame, text='⚙️ Export Quality')
        
        # Create scrollable content for export frame
        export_canvas = tk.Canvas(export_frame)
        export_scrollbar = ttk.Scrollbar(export_frame, orient='vertical', command=export_canvas.yview)
        export_scrollable_frame = tk.Frame(export_canvas)
        
        export_scrollable_frame.bind(
            '<Configure>',
            lambda e: export_canvas.configure(scrollregion=export_canvas.bbox('all'))
        )
        
        export_canvas.create_window((0, 0), window=export_scrollable_frame, anchor='nw')
        export_canvas.configure(yscrollcommand=export_scrollbar.set)
        
        tk.Label(export_scrollable_frame, text='Choose Export Quality Level:', font=('Arial', 10, 'bold')).pack(anchor='w', padx=10, pady=(10, 5))
        custom_var = tk.StringVar(value=preferences_data['customization_level'].get())
        
        # Create radio buttons for customization levels
        levels_frame = tk.Frame(export_scrollable_frame)
        levels_frame.pack(fill='x', padx=10, pady=(10, 0))
        
        custom_desc_var = tk.StringVar(value=CUSTOMIZATION_LEVELS['Default']['description'])
        
        def on_custom_change(*args):
            selected_level = custom_var.get()
            if selected_level in CUSTOMIZATION_LEVELS:
                custom_desc_var.set(CUSTOMIZATION_LEVELS[selected_level]['description'])
        
        for level in ['Default', 'Standard', 'Advanced', 'High Quality']:
            rb = tk.Radiobutton(levels_frame, text=level, variable=custom_var, value=level, command=on_custom_change, font=('Arial', 10))
            rb.pack(anchor='w', pady=6)
        
        custom_var.trace_add('write', on_custom_change)
        
        custom_desc_label = tk.Label(export_scrollable_frame, textvariable=custom_desc_var, wraplength=700, justify='left', foreground='#666666', font=('Arial', 9))
        custom_desc_label.pack(anchor='w', padx=10, pady=(15, 10))
        
        # Details for each level
        tk.Label(export_scrollable_frame, text='Features in Selected Quality Level:', font=('Arial', 9, 'bold')).pack(anchor='w', padx=10, pady=(5, 5))
        
        details_text = tk.Text(export_scrollable_frame, height=10, width=85, state='disabled', bg='#f5f5f5', relief='solid', padx=8, pady=6)
        details_text.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        def update_level_details(*args):
            selected_level = custom_var.get()
            if selected_level in CUSTOMIZATION_LEVELS:
                details_text.config(state='normal')
                details_text.delete('1.0', 'end')
                level_config = CUSTOMIZATION_LEVELS[selected_level]
                details = []
                for key, value in level_config.items():
                    if key != 'description' and isinstance(value, bool):
                        status = '✓' if value else '✗'
                        details.append(f'{status} {key.replace("_", " ").title()}')
                details_text.insert('end', '\n'.join(details))
                details_text.config(state='disabled')
        
        custom_var.trace_add('write', update_level_details)
        update_level_details()  # Initial display
        
        export_canvas.pack(side='left', fill='both', expand=True)
        export_scrollbar.pack(side='right', fill='y')
        
        # ===== TAB 3: RADIOREFERENCE API =====
        api_frame = ttk.Frame(notebook)
        notebook.add(api_frame, text='🔑 API Key')

        api_canvas = tk.Canvas(api_frame)
        api_scrollbar = ttk.Scrollbar(api_frame, orient='vertical', command=api_canvas.yview)
        api_scrollable_frame = tk.Frame(api_canvas)
        api_scrollable_frame.bind(
            '<Configure>',
            lambda e: api_canvas.configure(scrollregion=api_canvas.bbox('all'))
        )
        api_canvas.create_window((0, 0), window=api_scrollable_frame, anchor='nw')
        api_canvas.configure(yscrollcommand=api_scrollbar.set)

        tk.Label(api_scrollable_frame, text='RadioReference API Key', font=('Arial', 10, 'bold')).pack(anchor='w', padx=10, pady=(10, 8))
        tk.Label(api_scrollable_frame, text='Enter or manage your RadioReference API key for SOAP-backed repeater access.', wraplength=700, justify='left', fg='#666666', font=('Arial', 9)).pack(anchor='w', padx=10, pady=(0, 10))
        tk.Label(api_scrollable_frame, textvariable=preferences_data['api_status'], font=('Arial', 9, 'bold'), fg='#006600').pack(anchor='w', padx=10, pady=(0, 12))

        tk.Button(api_scrollable_frame, text='Enter API key...', command=lambda: handle_api_choice('Enter API key...'), bg='#1976D2', fg='white', width=20).pack(anchor='w', padx=10, pady=(0, 8))
        tk.Button(api_scrollable_frame, text='Use built-in encrypted key', command=lambda: handle_api_choice('Use built-in (encrypted)'), bg='#1976D2', fg='white', width=20).pack(anchor='w', padx=10, pady=(0, 12))

        tk.Label(api_scrollable_frame, text='After entering a key, the status above will update to Loaded.', wraplength=700, justify='left', fg='#666666', font=('Arial', 8)).pack(anchor='w', padx=10, pady=(0, 10))

        api_canvas.pack(side='left', fill='both', expand=True)
        api_scrollbar.pack(side='right', fill='y')
        
        # ===== TAB 4: SAFETY & STARTUP =====
        safety_frame = ttk.Frame(notebook)
        notebook.add(safety_frame, text='🛡️ Safety & Startup')
        
        # Create scrollable content for safety frame
        safety_canvas = tk.Canvas(safety_frame)
        safety_scrollbar = ttk.Scrollbar(safety_frame, orient='vertical', command=safety_canvas.yview)
        safety_scrollable_frame = tk.Frame(safety_canvas)
        
        safety_scrollable_frame.bind(
            '<Configure>',
            lambda e: safety_canvas.configure(scrollregion=safety_canvas.bbox('all'))
        )
        
        safety_canvas.create_window((0, 0), window=safety_scrollable_frame, anchor='nw')
        safety_canvas.configure(yscrollcommand=safety_scrollbar.set)
        
        safety_vars = {}
        
        tk.Label(safety_scrollable_frame, text='Startup & Safety Options:', font=('Arial', 10, 'bold')).pack(anchor='w', padx=10, pady=(10, 10))
        
        for key, setting in APP_SETTINGS.items():
            var = tk.BooleanVar(value=setting['default'])
            safety_vars[key] = var
            
            cb = tk.Checkbutton(safety_scrollable_frame, text=setting['label'], variable=var, font=('Arial', 10))
            cb.pack(anchor='w', padx=10, pady=4)
            
            desc = tk.Label(safety_scrollable_frame, text=setting['description'], font=('Arial', 8), fg='#666666', wraplength=700, justify='left')
            desc.pack(anchor='w', padx=30, pady=(0, 8))
        
        safety_canvas.pack(side='left', fill='both', expand=True)
        safety_scrollbar.pack(side='right', fill='y')
        
        # ===== TAB 4: ADVANCED TWEAKS =====
        tweaks_frame = ttk.Frame(notebook)
        notebook.add(tweaks_frame, text='🔧 Advanced Tweaks')
        
        # Create scrollable content for tweaks frame
        tweaks_canvas = tk.Canvas(tweaks_frame)
        tweaks_scrollbar = ttk.Scrollbar(tweaks_frame, orient='vertical', command=tweaks_canvas.yview)
        tweaks_scrollable_frame = tk.Frame(tweaks_canvas)
        
        tweaks_scrollable_frame.bind(
            '<Configure>',
            lambda e: tweaks_canvas.configure(scrollregion=tweaks_canvas.bbox('all'))
        )
        
        tweaks_canvas.create_window((0, 0), window=tweaks_scrollable_frame, anchor='nw')
        tweaks_canvas.configure(yscrollcommand=tweaks_scrollbar.set)
        
        tk.Label(tweaks_scrollable_frame, text='Frequency Validation Settings:', font=('Arial', 10, 'bold')).pack(anchor='w', padx=10, pady=(10, 10))
        
        tweak_vars = {}
        tweaks_config = {
            'strict_freq_check': {'label': 'Strict Frequency Checking', 'description': 'Reject any frequency outside defined bands'},
            'auto_step_optimize': {'label': 'Auto-optimize Step Sizes', 'description': 'Automatically adjust step sizes to radio capabilities'},
            'filter_narrow_band': {'label': 'Filter Narrow Band Only', 'description': 'Include narrow-band (FM-N) mode frequencies'},
            'sort_output': {'label': 'Sort Output by Frequency', 'description': 'Automatically sort channels by frequency in output'},
            'remove_all_dups': {'label': 'Aggressive Duplicate Removal', 'description': 'Remove near-duplicate frequencies within 5 kHz'},
        }
        
        for key, config in tweaks_config.items():
            var = tk.BooleanVar(value=False)
            tweak_vars[key] = var
            
            cb = tk.Checkbutton(tweaks_scrollable_frame, text=config['label'], variable=var, font=('Arial', 10))
            cb.pack(anchor='w', padx=10, pady=4)
            
            desc = tk.Label(tweaks_scrollable_frame, text=config['description'], font=('Arial', 8), fg='#666666', wraplength=700, justify='left')
            desc.pack(anchor='w', padx=30, pady=(0, 8))
        
        tweaks_canvas.pack(side='left', fill='both', expand=True)
        tweaks_scrollbar.pack(side='right', fill='y')
        
        # ===== Buttons at bottom =====
        button_frame = tk.Frame(pref_window)
        button_frame.pack(fill='x', padx=15, pady=(0, 15))
        
        def on_apply():
            preferences_data['selected_model'].set(model_var.get())
            preferences_data['selected_source'].set(source_var.get())
            preferences_data['customization_level'].set(custom_var.get())
            preferences_data['scanner_mode'].set(scanner_mode_var.get())
            preferences_data['frs_gmrs_unlock'].set(frs_pref_var.get())
            # Store safety/startup settings
            for key, var in safety_vars.items():
                APP_SETTINGS[key]['value'] = var.get()
            # Store tweak settings
            for key, var in tweak_vars.items():
                tweaks_config[key]['value'] = var.get()
            try:
                # enforce constraints immediately in main UI
                enforce_model_constraints()
            except Exception:
                pass
            save_persistent_settings({
                'selected_model': preferences_data['selected_model'].get(),
                'selected_source': preferences_data['selected_source'].get(),
                'customization_level': preferences_data['customization_level'].get(),
                'scanner_mode': preferences_data['scanner_mode'].get(),
                'frs_gmrs_unlock': preferences_data['frs_gmrs_unlock'].get(),
            })
            pref_window.destroy()
            messagebox.showinfo('Preferences', f'✓ Settings saved!\nRadio Model: {model_var.get()}\nQuality Level: {custom_var.get()}')
        
        def on_cancel():
            pref_window.destroy()
        
        tk.Button(button_frame, text='✓ Apply', command=on_apply, bg='#4CAF50', fg='white', width=12, font=('Arial', 10)).pack(side='right', padx=5)
        tk.Button(button_frame, text='Cancel', command=on_cancel, width=12, font=('Arial', 10)).pack(side='right', padx=5)

    
    prefmenu = tk.Menu(menubar, tearoff=0)
    prefmenu.add_command(label='Radio & Export Settings', command=open_preferences)
    menubar.add_cascade(label='Preferences', menu=prefmenu)

    # Attach Help menu after Preferences so order is File -> API -> Preferences -> Help
    menubar.add_cascade(label='Help', menu=helpmenu)
    root.config(menu=menubar)

    # Make window wider to fit content and provide an area on the right for a QR image
    root.geometry('1100x700')
    root.resizable(True, True)
    # Reserve a fixed right column for the QR image so it doesn't overlap inputs
    root.grid_columnconfigure(3, minsize=260, weight=0)

    # Load and display CashApp QR on the right-hand area if available
    try:
        img_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'media', 'CashApp_QR.png'))
        qr_img = None
        # Prefer PIL for reliable PNG handling and resizing
        try:
            from PIL import Image, ImageTk
            im = Image.open(img_path)
            im.thumbnail((360, 360))
            qr_img = ImageTk.PhotoImage(im)
        except Exception:
            try:
                # Fallback to Tk PhotoImage and subsample if needed
                tmp = tk.PhotoImage(file=img_path)
                w = tmp.width()
                h = tmp.height()
                max_dim = 360
                factor = 1
                if w > max_dim or h > max_dim:
                    # subsample accepts integer factors
                    factor = int(max(1, (w + max_dim - 1) // max_dim, (h + max_dim - 1) // max_dim))
                    tmp = tmp.subsample(factor, factor)
                qr_img = tmp
            except Exception:
                qr_img = None
        if qr_img:
            img_label = tk.Label(root, image=qr_img)
            img_label.image = qr_img
            # Grid the QR into the reserved right column so it cannot overlap the entry fields
            img_label.grid(row=0, column=3, rowspan=12, padx=12, pady=8, sticky='ne')

            # Separate clickable note under the QR code pointing to the Donations menu
            try:
                note = tk.Label(root, text='Donation options available in Help: Contact > Donations', wraplength=240, justify='center', font=('Arial', 9, 'underline'), fg='#0066cc', cursor='hand2')
                note.grid(row=12, column=3, padx=12, pady=(2,12), sticky='n')
                try:
                    note.bind('<Button-1>', lambda e: open_donations())
                except Exception:
                    pass
            except Exception:
                pass
    except Exception:
        pass

    def show_donation_dialog():
        dlg = tk.Toplevel(root)
        dlg.title('Support FreqFinder')
        dlg.geometry('450x180')
        dlg.grab_set()
        dlg.transient(root)
        dlg.resizable(False, False)
        dlg.lift()
        dlg.focus()
        dlg.attributes('-topmost', True)
        tk.Label(dlg, text="Please help pay for the numerous accounts, interfaces and time that I have spent on FreqFinder.", wraplength=410, justify='left', font=(None, 11)).pack(padx=20, pady=(18, 10))
        btn_frame = tk.Frame(dlg)
        btn_frame.pack(pady=(0, 16))

        def close_dialog():
            dlg.destroy()

        def open_donate():
            dlg.destroy()
            open_donations()

        tk.Button(btn_frame, text="Not Now", width=12, command=close_dialog).pack(side='left', padx=10)
        tk.Button(btn_frame, text="Donate", width=12, command=open_donate).pack(side='left', padx=10)

    # Show donation dialog on program open
    root.after(500, show_donation_dialog)

    # Create a reusable tooltip class for better user guidance
    class ToolTip:
        def __init__(self, widget, text, delay=1000):
            self.widget = widget
            self.text = text
            self.delay = delay
            self.tipwindow = None
            self.id = None
            self.x = self.y = 0
            self.widget.bind('<Enter>', self.on_enter, add=True)
            self.widget.bind('<Leave>', self.on_leave, add=True)
            self.widget.bind('<Motion>', self.on_motion, add=True)
        
        def on_enter(self, event=None):
            self.schedule()
        
        def on_leave(self, event=None):
            self.unschedule()
            self.hidetip()
        
        def on_motion(self, event=None):
            if self.tipwindow or not self.id:
                return
            self.x = event.x_root + 10
            self.y = event.y_root + 10
        
        def schedule(self):
            self.unschedule()
            self.id = self.widget.after(self.delay, self.showtip)
        
        def unschedule(self):
            if self.id:
                self.widget.after_cancel(self.id)
                self.id = None
        
        def showtip(self):
            if self.tipwindow or not self.text:
                return
            self.tipwindow = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f'+{self.x}+{self.y}')
            label = tk.Label(tw, text=self.text, background='#fffacd', relief='solid', borderwidth=1, 
                           font=('Arial', 9), wraplength=250, justify='left', padx=8, pady=6)
            label.pack(ipadx=1)
        
        def hidetip(self):
            if self.tipwindow:
                self.tipwindow.destroy()
                self.tipwindow = None

    # Input entries (accept either full Radioreference URL or a ZIP code)
    input_vars = [tk.StringVar() for _ in range(4)]
    resolved_labels = [tk.StringVar(value='') for _ in range(4)]

    # load radioref index (map normalized 'county, state' -> ctid)
    rr_index = {}
    try:
        import csv
        with open('radioref.csv', newline='', encoding='utf-8') as rf:
            reader = csv.DictReader(rf)
            for row in reader:
                title = row.get('location_title','').strip()
                # normalize: remove trailing 'Amateur Radio' and parenthetical abbrev
                t = re.sub(r'\s*Amateur Radio$', '', title)
                t = re.sub(r'\s*\([^)]*\)\s*$', '', t).strip()
                # include only entries that look like '... County, State' or '... City, State'
                if ',' in t and ('County' in t or 'City' in t):
                    key = t.lower()
                    rr_index[key] = row.get('id')
    except FileNotFoundError:
        rr_index = {}

    def resolve_input(idx):
        v = input_vars[idx].get().strip()
        if not v:
            resolved_labels[idx].set('')
            return
        # if full URL, try to extract location name from page
        if v.startswith('http://') or v.startswith('https://'):
            label = get_location_from_url(v) or ''
            resolved_labels[idx].set(label)
            return
        # if looks like ZIP code
        if re.match(r'^\d{5}$', v):
            # geocode via zippopotam.us -> then reverse geocode for county
            try:
                pr = http_get(f'http://api.zippopotam.us/us/{v}', timeout=6)
                pj = pr.json()
                places = pj.get('places', [])
                if places:
                    lat = places[0].get('latitude')
                    lon = places[0].get('longitude')
                    if lat and lon:
                        nom = http_get(
                            f'https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}',
                            headers={'User-Agent': 'chirp-scraper'},
                            timeout=8,
                        ).json()
                        addr = nom.get('address', {})
                        county = addr.get('county')
                        state = addr.get('state')
                        if county and state:
                            key = f"{county}, {state}".lower()
                            ctid = rr_index.get(key)
                            if ctid:
                                resolved_labels[idx].set(f"{county}, {state}  (ctid {ctid})")
                            else:
                                resolved_labels[idx].set(f"{county}, {state}  (no ctid)")
                            return
            except Exception:
                pass
        # otherwise, show raw value
        resolved_labels[idx].set('')

    for i, iv in enumerate(input_vars, start=1):
        label = tk.Label(root, text=f'Zip Code {i}:')
        label.grid(row=i-1, column=0, sticky='w')
        ToolTip(label, 'Enter a 5-digit ZIP code or RadioReference URL\nto search for frequencies in that area')
        
        ent = tk.Entry(root, textvariable=iv, width=12)
        ent.grid(row=i-1, column=1, sticky='w')
        ToolTip(ent, 'ZIP Code: Searches for repeaters in that area\nURL: Directly uses RadioReference page')
        
        # resolved label to the right
        resolved_lbl = tk.Label(root, textvariable=resolved_labels[i-1], width=40, anchor='w')
        resolved_lbl.grid(row=i-1, column=2, sticky='w')
        ToolTip(resolved_lbl, 'Shows the county/state location found\nand its RadioReference ID (ctid)')
        
        # trace changes
        iv.trace_add('write', lambda *_i, idx=i-1: resolve_input(idx))

    # Bands checkbuttons and listbox - place below the input boxes and stack vertically
    start_row = len(input_vars)
    bands_label = tk.Label(root, text='Available Bands:')
    bands_label.grid(row=start_row, column=0, padx=8, sticky='w')
    ToolTip(bands_label, 'Select which frequency bands to include\nin your exported CSV file')
    
    band_vars = {}
    band_listbox = tk.Listbox(root, height=len(BAND_RANGES))
    band_listbox.grid(row=start_row+1, column=1, rowspan=len(BAND_RANGES), sticky='n', padx=8, pady=4)
    ToolTip(band_listbox, 'Use Up/Down buttons to reorder bands\nTop band appears first in export')

    def toggle_band(band):
        if band_vars[band].get():
            band_listbox.insert(tk.END, band)
        else:
            # remove all occurrences
            for i in range(band_listbox.size()-1, -1, -1):
                if band_listbox.get(i) == band:
                    band_listbox.delete(i)

    for j, band in enumerate(BAND_RANGES.keys()):
        # default to select both common amateur bands 70cm and 2m
        v = tk.IntVar(value=1 if band in ('70cm', '2m') else 0)
        band_vars[band] = v
        cb = tk.Checkbutton(root, text=band, variable=v, command=lambda b=band: toggle_band(b))
        cb.grid(row=start_row+1+j, column=0, sticky='w', padx=8, pady=6)
        
        # Add band-specific tooltips
        if band == '70cm':
            ToolTip(cb, '70cm band (420-450 MHz)\nUltra High Frequency - local area coverage')
        elif band == '2m':
            ToolTip(cb, '2m band (144-148 MHz)\nVery High Frequency - wider area coverage')
        elif band == 'NOAA':
            ToolTip(cb, 'NOAA Weather Alerts (162.4-162.55 MHz)\nPublic weather radio broadcasts')
        elif band == 'MURS':
            ToolTip(cb, 'MURS (151.82-154.6 MHz)\nMulti-Use Radio Service - license-free')
        elif band == 'FRS/GMRS':
            ToolTip(cb, 'FRS/GMRS (462-467 MHz)\nFamily Radio Service / General Mobile Radio Service')
        elif band == 'Emergency':
            ToolTip(cb, 'Emergency / Public Safety dispatch frequencies\nSearches county/zip pages for Police/Fire/EMS analog channels')
        
        if v.get():
            band_listbox.insert(tk.END, band)

    # reorder buttons
    def move_up():
        sel = band_listbox.curselection()
        if not sel: return
        i = sel[0]
        if i == 0: return
        txt = band_listbox.get(i)
        band_listbox.delete(i)
        band_listbox.insert(i-1, txt)
        band_listbox.selection_set(i-1)

    def move_down():
        sel = band_listbox.curselection()
        if not sel: return
        i = sel[0]
        if i == band_listbox.size()-1: return
        txt = band_listbox.get(i)
        band_listbox.delete(i)
        band_listbox.insert(i+1, txt)
        band_listbox.selection_set(i+1)

    up_btn = tk.Button(root, text='Up', command=move_up)
    up_btn.grid(row=start_row+1+len(BAND_RANGES), column=1, sticky='w', padx=8)
    ToolTip(up_btn, 'Move selected band up in priority')
    
    down_btn = tk.Button(root, text='Down', command=move_down)
    down_btn.grid(row=start_row+1+len(BAND_RANGES), column=1, sticky='e', padx=8)
    ToolTip(down_btn, 'Move selected band down in priority')

    # Checkbox to ensure FRS/GMRS frequencies are treated as unlocked and enable bandplan
    frs_unlock_var = preferences_data.get('frs_gmrs_unlock') if preferences_data.get('frs_gmrs_unlock') else tk.IntVar(value=0)
    frs_unlock_cb = tk.Checkbutton(root, text='Ensure FRS/GMRS unlocked & enable bandplan', variable=frs_unlock_var)
    frs_unlock_cb.grid(row=start_row+1+len(BAND_RANGES)+1, column=0, sticky='w', padx=8, pady=4)
    ToolTip(frs_unlock_cb, 'Mark FRS/GMRS fixed channels as unlocked for programming (requires firmware unlock on your radio)')

    # Export button (centered at bottom)
    def on_export():
        if exporting_flag.get('running'):
            messagebox.showwarning('Export', 'An export is already running. Please wait.')
            return
        def cleanup_export():
            try:
                export_btn.config(state='normal')
            except Exception:
                pass
            exporting_flag['running'] = False
            try:
                _suppress_messageboxes(False)
            except Exception:
                pass
            try:
                _flush_dialog_queue()
            except Exception:
                pass

        exporting_flag['running'] = True
        # suppress dialogs while exporting to avoid per-row popups
        try:
            _suppress_messageboxes(True)
        except Exception:
            pass
        try:
            export_btn.config(state='disabled')
        except Exception:
            pass
        pages = {}
        # Require at least one ZIP code and one band selected
        selected_source = preferences_data.get('selected_source').get() if preferences_data.get('selected_source') else 'RadioReference'
        scanner_mode_enabled = bool(preferences_data.get('scanner_mode').get() if preferences_data.get('scanner_mode') else 0)
        zip_present = any(re.match(r'^\d{5}$', iv.get().strip() or '') for iv in input_vars)
        band_selected = any(v.get() for v in band_vars.values())
        if selected_source == 'Radio Browser':
            if not zip_present:
                messagebox.showerror('Error', 'Radio Browser source requires at least one valid ZIP code')
                cleanup_export()
                return
        else:
            if not zip_present or not band_selected:
                messagebox.showerror('Error', 'Must have at least one ZIP code and at least one band selected')
                cleanup_export()
                return

        if scanner_mode_enabled and selected_source != 'Radio Browser':
            # Scanner mode keeps NOAA/WX channels in the export, but will mark them skipped in the CSV.
            if band_vars.get('NOAA') and band_vars['NOAA'].get():
                messagebox.showinfo('Scanner mode', 'Scanner mode is enabled: NOAA/WX channels will be exported with the Scan/Skip flag set.')
        if selected_source == 'Radio Browser':
            rows_rb = []
            unique_zips = []
            for idx, iv in enumerate(input_vars):
                u = iv.get().strip()
                if not re.match(r'^\d{5}$', u):
                    continue
                if u not in unique_zips:
                    unique_zips.append(u)
                stations = get_radio_browser_broadcast_for_zip(u, limit=50)
                if not stations:
                    continue
                for station in stations:
                    rows_rb.append({
                        'ZIP': u,
                        'Name': station.get('name', ''),
                        'URL': station.get('url', ''),
                        'ResolvedURL': station.get('url_resolved', ''),
                        'Tags': station.get('tags', ''),
                        'Country': station.get('country', ''),
                        'State': station.get('state', ''),
                        'Codec': station.get('codec', ''),
                        'Bitrate': station.get('bitrate', ''),
                        'Language': station.get('language', ''),
                        'LastCheck': station.get('lastchecktime', ''),
                        'Latitude': station.get('geo_lat', ''),
                        'Longitude': station.get('geo_long', ''),
                    })
            if not rows_rb:
                messagebox.showerror('Error', 'No Radio Browser station results were found for the selected ZIPs.')
                cleanup_export()
                return
            try:
                from datetime import datetime
                default_name = 'FreqFinder_RadioBrowser_'
                if unique_zips:
                    default_name += '-'.join(unique_zips[:6])
                else:
                    default_name += 'stations'
                default_name += '_' + datetime.now().strftime('%b%Y') + '.csv'
            except Exception:
                default_name = 'FreqFinder_RadioBrowser.csv'
            initial_dir = DEFAULT_SAVE_DIR if os.path.isdir(DEFAULT_SAVE_DIR) else None
            save_path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV files','*.csv'),('All files','*.*')], initialdir=initial_dir, initialfile=default_name, title='Save Radio Browser station CSV as')
            if not save_path:
                cleanup_export()
                return
            try:
                df_rb = pd.DataFrame(rows_rb)
                df_rb.to_csv(save_path, index=False)
                messagebox.showinfo('Done', f'Wrote {len(rows_rb)} station rows to {save_path}')
            except Exception as e:
                messagebox.showerror('Error', f'Failed writing Radio Browser CSV: {e}')
            return

        for idx, iv in enumerate(input_vars):
            u = iv.get().strip()
            if not u:
                continue
            # if full URL provided, use it
            if u.startswith('http://') or u.startswith('https://'):
                pages[u] = u
                continue
            # if ZIP, try to map to ctid via rr_index
            if re.match(r'^\d{5}$', u):
                try:
                    pr = http_get(f'http://api.zippopotam.us/us/{u}', timeout=6)
                    if pr.status_code == 200:
                        pj = pr.json()
                        places = pj.get('places', [])
                        if places:
                            lat = places[0].get('latitude')
                            lon = places[0].get('longitude')
                            if lat and lon:
                                nom = http_get(
                                    f'https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}',
                                    headers={'User-Agent': 'chirp-scraper'},
                                    timeout=8,
                                ).json()
                                addr = nom.get('address', {})
                                county = addr.get('county')
                                state = addr.get('state')
                                if county and state:
                                    key = f"{county}, {state}".lower()
                                    ctid = rr_index.get(key)
                                    if ctid:
                                        pages[f"{county}, {state}"] = f'https://www.radioreference.com/db/browse/ctid/{ctid}/ham'
                                        continue
                except Exception:
                    pass
            # fallback: ignore
            continue
        if not pages:
            pages = {k: v for k, v in default_pages.items()}

        # selected bands in order
        sel_bands = [band_listbox.get(i) for i in range(band_listbox.size())]
        if not sel_bands:
            messagebox.showerror('Error', 'Select at least one band to export')
            cleanup_export()
            return

        # Determine selected model and customization level for filtering
        sel_name = preferences_data.get('selected_model').get() if preferences_data.get('selected_model') else 'Generic'
        model_key = next((k for k, v in RADIO_MODELS.items() if v['name'] == sel_name), 'Generic')
        model_obj = RADIO_MODELS.get(model_key, RADIO_MODELS['Generic'])
        cust_level = preferences_data.get('customization_level').get() if preferences_data.get('customization_level') else 'Default'

        # run scraping and filter by selected bands
        rows = []
        fetch_errors = []
        # Skip showing a fetch progress window; perform fetching silently
        fetch_total = max(1, len(pages))
        fetch_progress = 0
        fetch_bar = None
        fetch_status = None

        page_idx = 0
        for c, u in pages.items():
            try:
                page_rows = list(fetch_freqs_for_page(u))
                if not page_rows:
                    fetch_errors.append((c, u, 'No repeater rows returned'))
                for tup in page_rows:
                    # unpack flexible return (name,freq,tone[,duplex_hint,offset_hint])
                    if len(tup) >= 5:
                        name, f, tone, duplex_hint, offset_hint = tup[0], tup[1], tup[2], tup[3], tup[4]
                    else:
                        name, f, tone = tup[0], tup[1], tup[2]
                        duplex_hint, offset_hint = (None, None)
                    # determine which band this frequency belongs to (first matching selected band)
                    band_label = None
                    # Special-case: Emergency matching by keyword or common public-safety ranges
                    try:
                        if 'Emergency' in sel_bands:
                            lname = (name or '').lower()
                            detected_protocol = None
                            # base keywords
                            emergency_keywords = ['dispatch', 'police', 'fire', 'sheriff', 'ems', 'ambulance', 'emergency', 'public safety']
                            # digital protocol tokens
                            p25_tokens = ['p25', 'project 25']
                            edacs_tokens = ['edacs']
                            other_digital = ['dmr', 'nxdn', 'tdma', 'trunk', 'trunking', 'digital']

                            match = False
                            # keyword match (loose)
                            for kw in emergency_keywords:
                                if kw in lname:
                                    match = True
                                    break

                            # frequency-range match (always allowed)
                            if not match:
                                for lo, hi in BAND_RANGES.get('Emergency', []):
                                    try:
                                        if lo <= float(f) <= hi:
                                            match = True
                                            break
                                    except Exception:
                                        continue

                            # Advanced: tighten matching and allow P25/EDACS detection
                            if match and cust_level in ('Advanced', 'High Quality'):
                                # detect explicit protocol tokens
                                if any(t in lname for t in p25_tokens):
                                    detected_protocol = 'P25'
                                elif any(t in lname for t in edacs_tokens):
                                    detected_protocol = 'EDACS'
                                # if other digital types are present and model does not support general digital, skip
                                if any(t in lname for t in other_digital) and not model_obj.get('supports_digital_mode'):
                                    match = False

                            # Final acceptance: if protocol detected, ensure model supports it (only in advanced)
                            if detected_protocol:
                                if detected_protocol == 'P25' and not model_obj.get('supports_p25'):
                                    match = False
                                if detected_protocol == 'EDACS' and not model_obj.get('supports_edacs'):
                                    match = False

                            # If matched and not rejected by digital incompatibility, mark Emergency
                            if match:
                                # if we detected a protocol, attach it to the tuple via a small wrapper by setting band_label
                                band_label = 'Emergency'
                                # store detected protocol into a temporary variable attached to name for later propagation
                                if detected_protocol:
                                    name = f"{name} [{detected_protocol}]"
                    except Exception:
                        pass
                    for band in sel_bands:
                        ranges = BAND_RANGES.get(band, [])
                        for lo, hi in ranges:
                            try:
                                if lo <= float(f) <= hi:
                                    band_label = band
                                    break
                            except Exception:
                                continue
                        if band_label:
                            break
                    if not band_label:
                        continue
                    rows.append({'Name': name, 'Frequency': f, 'Duplex': None, 'Tone': tone, 'Comment': c, 'Band': band_label, 'duplex_hint': duplex_hint, 'offset_hint': offset_hint})
            except Exception as exc:
                fetch_errors.append((c, u, str(exc)))

        if fetch_errors:
            warning_text = 'Some RadioReference pages could not be fetched or parsed.\n'
            warning_text += 'Only fixed-band NOAA/MURS/FRS-GMRS rows may be available.\n\n'
            warning_text += '\n'.join(f'{label}: {err}' for label, _, err in fetch_errors[:5])
            if len(fetch_errors) > 5:
                warning_text += f'\n...and {len(fetch_errors)-5} more.'
            try:
                messagebox.showwarning('RadioReference fetch warning', warning_text)
            except Exception:
                print(warning_text)
        
        # update fetch progress after each page processed
        try:
            page_idx += 1
            # no fetch progress UI when running silently
            pass
        except Exception:
            pass

        # If NOAA band selected, include NOAA weather frequencies from CSV
        if 'NOAA' in sel_bands:
            for entry in NOAA_FREQS:
                name, f, tone, raw = entry
                rows.append({'Name': name or f'NOAA {f}', 'Frequency': f, 'Duplex': '', 'Tone': tone or '', 'Comment': 'Weather', 'Band': 'NOAA'})

        # If MURS selected, include fixed MURS channels from CSV
        if 'MURS' in sel_bands:
            for entry in MURS_FREQS:
                name, f, tone, raw = entry
                rows.append({'Name': name or f'MURS {f}', 'Frequency': f, 'Duplex': '', 'Tone': tone or '', 'Comment': 'MURS', 'Band': 'MURS'})

        # If FRS/GMRS selected, include fixed channels from CSV
        if 'FRS/GMRS' in sel_bands:
            for entry in FRS_GMRS_FREQS:
                name, f, duplex, tone, raw = entry
                rows.append({'Name': name or f'Channel {f}', 'Frequency': f, 'Duplex': duplex or '', 'Tone': tone or '', 'Comment': 'FRS/GMRS', 'Band': 'FRS/GMRS'})

        # sort rows by band order then frequency
        band_order = {b: i for i, b in enumerate(sel_bands)}
        rows.sort(key=lambda r: (band_order.get(r.get('Band'), 999), r.get('Frequency', 0)))

        # build CHIRP-like CSV with proper repeater handling (duplex/offset/tone)
        def compute_offset_local(freq):
            try:
                f = float(freq)
            except Exception:
                return ''
            if f >= 420.0:
                return '5.000'
            if 144.0 <= f < 148.0:
                return '0.600'
            return ''

        def parse_tone_local(tone_text):
            if not tone_text:
                return ('', '', '')
            t = tone_text.strip()
            if t.upper() == 'CSQ':
                return ('CSQ', '', '')
            m = re.search(r"([0-9]+\.?[0-9]*)", t)
            if m:
                try:
                    valf = float(m.group(1))
                except Exception:
                    return ('', '', '')
                # accept only plausible CTCSS tone frequencies
                if not (50.0 <= valf <= 260.0):
                    return ('', '', '')
                val = f"{valf:.1f}"
                return ('Tone', val, val)
            return (t, '', '')

        # Determine selected model object for compatibility filtering
        sel_name = preferences_data.get('selected_model').get() if preferences_data.get('selected_model') else 'Generic'
        model_key = next((k for k, v in RADIO_MODELS.items() if v['name'] == sel_name), 'Generic')
        model_obj = RADIO_MODELS.get(model_key, RADIO_MODELS['Generic'])

        df_rows = []
        for r in rows:
            name = r.get('Name','')
            freq = r.get('Frequency','')
            band = r.get('Band','')
            # Determine duplex: use frequency heuristic (>=147 -> +) rather than a 'Repeaters' band
            duplex = '+' if (isinstance(freq, (int,float)) and freq >= 147) else '-' if isinstance(freq, (int,float)) and freq < 147 else ''
            offset = compute_offset_local(freq) if duplex == '+' else ''
            tone_label, rTone, cTone = parse_tone_local(r.get('Tone',''))
            dtcs = '023' if rTone else ''
            dtcs_pol = 'NN' if rTone else ''
            # Remove scanned entries that lack an rTone value. Preserve fixed band lists (NOAA/MURS/FRS_GMRS).
            # Treat 'Emergency' like other scanned bands (require tone/validation similar to 2m/70cm).
            if not rTone and band not in ('NOAA', 'MURS', 'FRS/GMRS'):
                continue
            # For Emergency entries, allow P25/EDACS when supported and when in Advanced quality;
            # allow analog emergency channels even without tone. Filter other digital types unless model supports them.
            if band == 'Emergency':
                lname = (name or '').lower()
                # If annotated with detected protocol (from earlier), respect it
                protocol = None
                m = re.search(r'\[(P25|EDACS)\]$', name)
                if m:
                    protocol = m.group(1)
                # If protocol present, ensure model supports it and that advanced quality is selected
                if protocol:
                    if cust_level not in ('Advanced', 'High Quality'):
                        continue
                    if protocol == 'P25' and not model_obj.get('supports_p25'):
                        continue
                    if protocol == 'EDACS' and not model_obj.get('supports_edacs'):
                        continue
                else:
                    # no explicit protocol: if entry references other digital trunking (DMR/NXDN/etc), allow only when model has digital support and advanced quality
                    other_digital = ('dmr', 'nxdn', 'tdma', 'trunk', 'trunking', 'digital')
                    if any(d in lname for d in other_digital):
                        if not model_obj.get('supports_digital_mode') or cust_level not in ('Advanced', 'High Quality'):
                            continue
            skip_value = ''
            if scanner_mode_enabled and band == 'NOAA':
                skip_value = 'Yes'
            df_rows.append({
                'Name': name,
                'Frequency': freq,
                'Duplex': duplex,
                'Offset': offset,
                'Tone': tone_label,
                'rToneFreq': rTone,
                'cToneFreq': cTone,
                'DtcsCode': dtcs,
                'DtcsPolarity': dtcs_pol,
                'Mode': 'FM',
                'TStep': 5,
                'Skip': skip_value,
                'Comment': r.get('Comment','')
            })

        # Create progress window
        progress_window = tk.Toplevel(root)
        progress_window.title('Exporting CSV')
        progress_window.geometry('400x120')
        progress_window.resizable(False, False)
        progress_window.transient(root)

        center_and_clamp(progress_window, 400, 120)

        progress_label = tk.Label(progress_window, text='Processing and building CSV...', wraplength=380)
        progress_label.pack(pady=10)

        progress_bar = ttk.Progressbar(progress_window, mode='indeterminate', length=360)
        progress_bar.pack(pady=10, padx=20)
        progress_bar.start()

        progress_status = tk.Label(progress_window, text='', font=('Arial', 9))
        progress_status.pack(pady=5)

        def update_progress(msg):
            progress_status.config(text=msg)
            progress_window.update()
        
        try:
            import pandas as pd
            update_progress('Building DataFrame...')
            outdf = pd.DataFrame(df_rows)
            # ensure columns
            cols = ["Name","Frequency","Duplex","Offset","Tone","rToneFreq","cToneFreq","DtcsCode","DtcsPolarity","Mode","TStep","Skip","Comment"]
            for c in cols:
                if c not in outdf.columns:
                    outdf[c] = ''
            outdf = outdf[cols]
            outdf.index = range(1, len(outdf)+1)
            outdf.index.name = 'Location'
            
            update_progress(f'Preparing {len(outdf)} rows...')
            
            # Store data for Save As functionality
            exported_data['dataframe'] = outdf
            exported_data['row_count'] = len(outdf)
            exported_data['pages'] = pages
            
            # Ask user where to save the CSV
            progress_bar.stop()
            progress_label.config(text='Choose save location...')
            progress_window.update()

            # Build sensible default filename: Chirp_$Model_$Zipcode[#]_$Month
            try:
                from datetime import datetime
                import csv as _csv
                # model
                model_raw = preferences_data.get('selected_model').get() if preferences_data.get('selected_model') else 'Generic'
                model_s = re.sub(r'[^A-Za-z0-9]+', '_', model_raw).strip('_') or 'Model'

                # try to find zip codes in pages labels/urls
                zip_candidates = []
                for k, v in pages.items():
                    m1 = re.search(r"(\d{5})", str(k))
                    m2 = re.search(r"(\d{5})", str(v))
                    if m1:
                        zip_candidates.append(m1.group(1))
                    elif m2:
                        zip_candidates.append(m2.group(1))
                unique_zips = []
                for z in zip_candidates:
                    if z not in unique_zips:
                        unique_zips.append(z)
                if unique_zips:
                    if len(unique_zips) <= 6:
                        zip_part = '-'.join(unique_zips)
                    else:
                        zip_part = f"{unique_zips[0]}[{len(unique_zips)}]"
                else:
                    # fallback to first page label sanitized
                    first_label = next(iter(pages.keys()), 'Location')
                    zip_part = re.sub(r'[^A-Za-z0-9]+', '_', first_label).strip('_')

                month_part = datetime.now().strftime('%b%Y')
                default_name = f"FreqFinder_{model_s}_{zip_part}_{month_part}.csv"
            except Exception:
                default_name = output_path or 'chirp_output.csv'

            initial_dir = DEFAULT_SAVE_DIR if os.path.isdir(DEFAULT_SAVE_DIR) else None
            save_path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV files','*.csv'),('All files','*.*')], initialdir=initial_dir, initialfile=default_name, title='Save CSV as')
            if not save_path:
                progress_window.destroy()
                return

            # Write CSV row-by-row so we can show determinate progress
            try:
                import csv as _csv
                total = len(outdf)
                progress_bar.config(mode='determinate', maximum=total, value=0)
                update_progress(f'Writing 0/{total} rows...')
                # write with explicit Location column (index)
                fieldnames = ['Location'] + list(outdf.columns)
                with open(save_path, 'w', newline='', encoding='utf-8') as wf:
                    writer = _csv.DictWriter(wf, fieldnames=fieldnames)
                    writer.writeheader()
                    i = 0
                    out_cols = list(outdf.columns)
                    for i, row_tup in enumerate(outdf.itertuples(index=True, name=None), start=1):
                        rec = {'Location': row_tup[0]}
                        for c, v in zip(out_cols, row_tup[1:]):
                            rec[c] = v
                        writer.writerow(rec)
                        progress_bar['value'] = i
                        update_progress(f'Writing {i}/{total} rows...')
                progress_window.destroy()
                messagebox.showinfo('Done', f'Wrote {total} rows to {save_path}')
            except Exception as e:
                progress_window.destroy()
                messagebox.showerror('Error', f'Failed writing CSV: {e}')
        except Exception as e:
            try:
                progress_window.destroy()
            except Exception:
                pass
            messagebox.showerror('Error', f'Failed to export CSV: {e}')
        finally:
            # restore messagebox behavior and flush any queued dialogs
            try:
                _suppress_messageboxes(False)
            except Exception:
                pass
            try:
                _flush_dialog_queue()
            except Exception:
                pass
            exporting_flag['running'] = False
            try:
                export_btn.config(state='normal')
            except Exception:
                pass

    # Add Model-Specific Options Frame
    model_options_row = start_row + 1 + len(BAND_RANGES) + 3
    model_frame = tk.LabelFrame(root, text='Radio Model Options', padx=10, pady=8, font=('Arial', 10))
    model_frame.grid(row=model_options_row, column=0, columnspan=4, sticky='ew', padx=8, pady=(8, 0))
    
    # Display current selected model and quality level
    model_info_var = tk.StringVar(value='Model: Generic | Quality: Default')
    model_info_label = tk.Label(model_frame, textvariable=model_info_var, font=('Arial', 9), fg='#333333')
    model_info_label.pack(anchor='w', pady=5)
    
    model_features_var = tk.StringVar(value='Features: CTCSS Tones • DTCS • Duplex • Offset')
    model_features_label = tk.Label(model_frame, textvariable=model_features_var, font=('Arial', 8), fg='#666666')
    model_features_label.pack(anchor='w', pady=0)
    
    # Create a helper to update the model info display
    def update_model_display_main():
        model_key = None
        for key, model in RADIO_MODELS.items():
            if model['name'] == preferences_data['selected_model'].get():
                model_key = key
                break
        if model_key:
            model_obj = RADIO_MODELS[model_key]
            quality = preferences_data['customization_level'].get()
            model_info_var.set(f"Model: {model_obj['name'].replace('Anytone ', '')} | Quality: {quality}")
            
            # Build features string
            features = []
            if model_obj.get('supports_tone'):
                features.append('CTCSS Tones')
            if model_obj.get('supports_dtcs'):
                features.append('DTCS')
            if model_obj.get('supports_duplex'):
                features.append('Duplex')
            if model_obj.get('supports_offset'):
                features.append('Offset')
            if model_obj.get('supports_color_code'):
                features.append('Color Code')
            if model_obj.get('supports_timeslot'):
                features.append('Timeslot')
            model_features_var.set('Features: ' + ' • '.join(features))

    # Enforce model constraints on UI controls (bands and tweak options)
    def enforce_model_constraints():
        # Determine selected model key
        model_key = None
        sel_name = preferences_data.get('selected_model').get() if preferences_data.get('selected_model') else None
        for key, model in RADIO_MODELS.items():
            if model['name'] == sel_name:
                model_key = key
                break
        model_obj = RADIO_MODELS.get(model_key) if model_key else RADIO_MODELS.get('Generic')

        # Define basic requirements for bands -> required features (any-of semantics)
        BAND_FEATURE_REQUIREMENTS = {
            'MURS': {'requires_any': ['supports_tone', 'supports_mode']},
            'FRS/GMRS': {'requires_any': ['supports_duplex', 'supports_offset', 'supports_mode']},
            'NOAA': {'requires_any': ['supports_mode', 'supports_tone']},
            'Emergency': {'requires_any': ['supports_mode', 'supports_tone', 'supports_duplex']},
        }

        # Disable or enable band checkbuttons based on model capabilities
        for band, cb in band_checkbuttons.items():
            req = BAND_FEATURE_REQUIREMENTS.get(band)
            disabled = False
            if req and model_obj:
                any_ok = False
                for feat in req.get('requires_any', []):
                    if model_obj.get(feat):
                        any_ok = True
                        break
                disabled = not any_ok
            try:
                cb.config(state='disabled' if disabled else 'normal')
                # if disabling, also uncheck and remove from listbox
                if disabled:
                    try:
                        # uncheck variable
                        if band_vars.get(band):
                            band_vars[band].set(0)
                        for i in range(band_listbox.size()-1, -1, -1):
                            if band_listbox.get(i) == band:
                                band_listbox.delete(i)
                    except Exception:
                        pass
            except Exception:
                pass

        # Map tweak options to required model features (disable if unsupported)
        OPTION_REQUIREMENTS = {
            'auto_step_optimize': 'supports_step',
            'filter_narrow_band': 'supports_mode',
            'remove_all_dups': None,
            'strict_freq_check': None,
        }
        try:
            tcb = tweak_checkbuttons
            for key, cb in tcb.items():
                req_feat = OPTION_REQUIREMENTS.get(key)
                if req_feat and model_obj and not model_obj.get(req_feat):
                    try:
                        cb.config(state='disabled')
                        tweak_vars.get(key).set(False)
                    except Exception:
                        pass
                else:
                    try:
                        cb.config(state='normal')
                    except Exception:
                        pass
        except Exception:
            # tweaks UI not present yet; ignore
            pass
    
    # Bind preferences data changes to update display (periodically check)
    def check_model_change():
        update_model_display_main()
        try:
            enforce_model_constraints()
        except Exception:
            pass
        root.after(1000, check_model_change)  # Check every second for changes
    
    check_model_change()

    # compute export row and place button centered across columns
    export_row = model_options_row + 2
    root.grid_rowconfigure(export_row, weight=0)
    
    export_btn = tk.Button(root, text='Export CSV', command=on_export, bg='#4CAF50', fg='white', height=2, font=('Arial', 11, 'bold'))
    export_btn.grid(row=export_row, column=0, columnspan=4, pady=12, sticky='ew', padx=8)
    ToolTip(export_btn, 'Export scraped frequencies to CHIRP CSV file\nfor programming into your radio')

    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description="Scrape RadioReference ham pages and produce FreqFinder-compatible CSV")
    parser.add_argument('--pages', '-p', nargs='+', help='ZIP codes or Radioreference URLs (space separated)')
    parser.add_argument('--output', '-o', default=DEFAULT_OUTPUT_FILE, help='Output CSV file')
    parser.add_argument('--source', choices=['radioreference', 'radio_browser'], default='radioreference', help='Choose data source: RadioReference for repeater frequencies, or public Radio Browser for broadcast station metadata')
    parser.add_argument('--include-broadcast', action='store_true', help='When using RadioReference, also show Radio Browser station metadata for each ZIP code state')
    parser.add_argument('--delay', type=float, default=0.0, help='Seconds to wait between HTTP requests to avoid rate limits or blocking')
    parser.add_argument('--qrz-stub', action='store_true', help='Print QRZ helper stub status and exit')
    # GUI is the default; removed '--no-gui' option per request
    parser.add_argument('--prompt', action='store_true', help='Force interactive prompt for pages')
    parser.add_argument('--callsign-col', type=int, default=2, help='Column index for callsign/license (0-based)')
    parser.add_argument('--desc-col', type=int, default=7, help='Preferred column index for description (0-based)')
    parser.add_argument('--tone-col', type=int, default=4, help='Column index for tone (0-based)')
    parser.add_argument('--gui', action='store_true', help='Launch GUI to enter ZIPs and select bands')
    args = parser.parse_args()

    global REQUEST_DELAY_SECONDS
    REQUEST_DELAY_SECONDS = float(args.delay or os.environ.get('FREQFINDER_REQUEST_DELAY', REQUEST_DELAY_SECONDS) or 0)
    if REQUEST_DELAY_SECONDS > 0:
        print(f'Using {REQUEST_DELAY_SECONDS:.2f}s delay between HTTP requests to avoid rate limiting.')

    rows = []
    # determine pages dict
    if args.pages:
        tokens = args.pages
        pages = {}
        for t in tokens:
            if t.startswith('http://') or t.startswith('https://'):
                label = get_location_from_url(t) or t
                pages[label] = t
            else:
                # map ZIP to county page
                zip_pages = map_zips_to_counties([t])
                pages.update(zip_pages)
    else:
        if args.prompt:
            pages = get_pages_from_user()
            if not pages:
                pages = DEFAULT_PAGES
        else:
            pages = DEFAULT_PAGES

    if args.qrz_stub:
        helper = QRZHelper()
        print('QRZ helper stub loaded.')
        print('Login supported:', bool(helper.username or helper.password or helper.api_key))
        print('Query example:', helper.lookup_callsign('K7ABC'))
        return

    if args.source == 'radio_browser':
        rows = []
        if not args.pages:
            print('ERROR: --source radio_browser requires one or more ZIP codes passed via --pages')
            return
        for token in args.pages:
            if not re.fullmatch(r'\d{5}', token):
                print(f'Skipping non-ZIP token for radio_browser source: {token}')
                continue
            stations = get_radio_browser_broadcast_for_zip(token, limit=50)
            if not stations:
                print(f'No Radio Browser station metadata found for ZIP {token}')
                continue
            print(f'Radio Browser found {len(stations)} stations for ZIP {token} state')
            for station in stations:
                rows.append({
                    'ZIP': token,
                    'Name': station.get('name', ''),
                    'URL': station.get('url', ''),
                    'ResolvedURL': station.get('url_resolved', ''),
                    'Tags': station.get('tags', ''),
                    'Country': station.get('country', ''),
                    'State': station.get('state', ''),
                    'Codec': station.get('codec', ''),
                    'Bitrate': station.get('bitrate', ''),
                    'Language': station.get('language', ''),
                    'LastCheck': station.get('lastchecktime', ''),
                    'Latitude': station.get('geo_lat', ''),
                    'Longitude': station.get('geo_long', ''),
                })
        if rows:
            df = pd.DataFrame(rows)
            df.to_csv(args.output, index=False)
            print(f'Wrote {len(rows)} Radio Browser rows to {args.output}')
        else:
            print('No Radio Browser rows to write.')
        return

    if args.include_broadcast and args.pages:
        found_any = False
        for token in args.pages:
            if re.fullmatch(r'\d{5}', token):
                stations = get_radio_browser_broadcast_for_zip(token, limit=20)
                if stations:
                    found_any = True
                    print(f"Radio Browser found {len(stations)} stations for ZIP {token} state")
                    for station in stations[:10]:
                        print(f"  {station.get('name','<unknown>')} - {station.get('url_resolved','')} - tags={station.get('tags','')}")
        if not found_any:
            print('No Radio Browser station metadata found for the requested ZIP codes.')

    # GUI is default whenever a desktop session is available; otherwise run CLI.
    if gui_session_available():
        try:
            launch_gui_and_run(DEFAULT_PAGES, args.output)
            return
        except Exception as e:
            print(f'GUI startup failed ({e}); running in CLI mode')
    else:
        print('GUI not available: tkinter is not installed in this Python environment; running in CLI mode')
    for c,u in pages.items():
        for tup in scrape_rr(u):
            if len(tup) >= 5:
                name, f, tone, duplex_hint, offset_hint = tup[0], tup[1], tup[2], tup[3], tup[4]
            else:
                name, f, tone = tup[0], tup[1], tup[2]
                duplex_hint, offset_hint = (None, None)
            # determine duplex by hint or frequency heuristic
            try:
                freq_val = float(f)
            except Exception:
                freq_val = None
            if duplex_hint:
                duplex = duplex_hint
            else:
                duplex = '-' if (freq_val is not None and freq_val < 147) else '+'
            offset = ''
            if offset_hint:
                try:
                    offset = f"{float(offset_hint):.3f}"
                except Exception:
                    offset = ''
            else:
                if freq_val is not None and duplex == '+':
                    if freq_val >= 420.0:
                        offset = '5.000'
                    elif 144.0 <= freq_val < 148.0:
                        offset = '0.600'
            rows.append({
                "Location":name[:8],
                "Name":name,
                "Frequency":f,
                "Duplex":duplex,
                "Offset":offset,
                "Tone":tone,
                "Mode":"FM",
                "Power":"High",
                "Comment":c
            })
    for n, f, *_ in NOAA_FREQS:
        rows.append({"Name":n,"Frequency":f,
                     "Duplex":"","Offset":"","Tone":"","rToneFreq":"","cToneFreq":"","DtcsCode":"","DtcsPolarity":"","Mode":"FM","TStep":5,"Skip":"","Comment":"Weather"})

    # Build DataFrame with CHIRP-like layout. Use index named 'Location' starting at 1.
    df = pd.DataFrame(rows)
    # Ensure columns order matches expected layout
    cols = ["Name","Frequency","Duplex","Offset","Tone","rToneFreq","cToneFreq","DtcsCode","DtcsPolarity","Mode","TStep","Skip","Comment"]
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    df = df[cols]

    # Post-process each row: compute Offset and tone numeric fields
    def compute_offset(freq, duplex):
        try:
            f = float(freq)
        except Exception:
            return ""
        if f >= 420.0:
            return "5.000"
        if 144.0 <= f < 148.0:
            return "0.600"
        return ""

    def parse_tone(tone_text):
        if not tone_text:
            return ("", "", "")
        t = tone_text.strip()
        if t.upper() == 'CSQ':
            return ('CSQ', '', '')
        # try extract numeric tone
        m = re.search(r"([0-9]+\.?[0-9]*)", t)
        if m:
            try:
                valf = float(m.group(1))
            except Exception:
                return ('', '', '')
            if not (50.0 <= valf <= 260.0):
                return ('', '', '')
            val = f"{valf:.1f}"
            return ('Tone', val, val)
        return (t, '', '')

    processed = []
    for r in df.to_dict(orient='records'):
        name = r['Name']
        freq = r['Frequency']
        duplex = r['Duplex'] if r['Duplex'] is not None else ("-" if (isinstance(freq, (int,float)) and freq<147) else "+")
        offset = r['Offset'] or compute_offset(freq, duplex)
        tone_label, rTone, cTone = parse_tone(r.get('Tone',''))
        dtcs = '023' if rTone else ''
        dtcs_pol = 'NN' if rTone else ''
        processed.append({
            'Name': name,
            'Frequency': freq,
            'Duplex': duplex,
            'Offset': offset,
            'Tone': tone_label,
            'rToneFreq': rTone,
            'cToneFreq': cTone,
            'DtcsCode': dtcs,
            'DtcsPolarity': dtcs_pol,
            'Mode': r.get('Mode','FM'),
            'TStep': 5,
            'Skip': r.get('Skip',''),
            'Comment': r.get('Comment','')
        })

    out_df = pd.DataFrame(processed)
    # set index starting at 1 and name it 'Location'
    out_df.index = range(1, len(out_df) + 1)
    out_df.index.name = 'Location'
    out_df.to_csv(args.output)
    print(f'Wrote {len(out_df)} rows to {args.output}')

if __name__=="__main__":
    main()
