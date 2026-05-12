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

# Application version is read from setup.py if available.

def get_app_version():
    version = '0.1.0'
    try:
        setup_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'setup.py')
        if os.path.exists(setup_path):
            with open(setup_path, 'r', encoding='utf-8') as fp:
                text = fp.read()
            match = re.search(r"version\s*=\s*['\"]([^'\"]+)['\"]", text)
            if match:
                version = match.group(1)
    except Exception:
        pass
    return version

APP_VERSION = get_app_version()

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
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
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
    'preview_mode': 1,
    'strict_freq_check': 0,
    'auto_step_optimize': 0,
    'filter_narrow_band': 0,
    'sort_output': 0,
    'remove_all_dups': 0,
    'band_profiles': {},
    'last_band_profile': '',
    'last_opened_profile': '',
    'last_zip_entries': [],
    'recent_zip_sets': [],
    'last_step_size': 5,
    'scheduled_refresh': 0,
    'offline_cache': 0,
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


def save_persistent_settings(settings):
    try:
        import json
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as sf:
            json.dump(settings, sf, indent=2)
    except Exception:
        pass


def save_last_user_state(profile_name, zip_values):
    try:
        settings = load_persistent_settings()
        settings['last_band_profile'] = profile_name if profile_name else settings.get('last_band_profile', '')
        settings['last_opened_profile'] = profile_name if profile_name else settings.get('last_opened_profile', '')
        current_zips = [z for z in zip_values if z]
        settings['last_zip_entries'] = current_zips
        if current_zips:
            recent = settings.get('recent_zip_sets', [])
            if current_zips not in recent:
                recent.insert(0, current_zips)
                settings['recent_zip_sets'] = recent[:10]
        save_persistent_settings(settings)
    except Exception:
        pass

def http_get_with_retry(url, timeout=15, headers=None, delay=None, max_retries=3, **kwargs):
    """Enhanced HTTP GET helper with exponential backoff retry logic.
    
    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
        headers: Optional custom headers
        delay: Optional delay between requests
        max_retries: Maximum number of retry attempts
        **kwargs: Additional arguments for requests
        
    Returns:
        requests.Response object or raises exception
    """
    import random
    global _last_http_get_timestamp
    if delay is None:
        delay = REQUEST_DELAY_SECONDS
    if delay and _last_http_get_timestamp is not None:
        elapsed = time.monotonic() - _last_http_get_timestamp
        if elapsed < delay:
            time.sleep(delay - elapsed)

    req_headers = DEFAULT_HEADERS if headers is None else headers
    
    for attempt in range(max_retries):
        try:
            resp = HTTP_SESSION.get(url, headers=req_headers, timeout=timeout, **kwargs)
            _last_http_get_timestamp = time.monotonic()
            
            # Check for specific error conditions
            if resp.status_code == 405 and 'Human Verification' in resp.text:
                logger.error(f"Human verification required for {url}")
                raise RuntimeError(
                    'RadioReference blocked access with human verification. '
                    'This means automated scraping is not currently allowed from this environment. '
                    'Use the Radio Browser source in Preferences, or provide a direct API-backed source.'
                )
            
            # Handle rate limiting
            if resp.status_code in (429, 503):
                if attempt + 1 < max_retries:
                    wait_time = (2 ** attempt) + random.uniform(0.5, 1.5)
                    logger.warning(f"Rate limited (status {resp.status_code}), retry {attempt + 1}/{max_retries} after {wait_time:.1f}s")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Rate limiting exceeded after {max_retries} attempts for {url}")
                    raise requests.RequestException(f"Rate limiting exceeded: HTTP {resp.status_code}")
            
            # Handle forbidden requests
            if resp.status_code == 403:
                if attempt + 1 < max_retries:
                    wait_time = (2 ** attempt) + random.uniform(1.0, 2.0)
                    logger.warning(f"Access forbidden (403), retry {attempt + 1}/{max_retries} after {wait_time:.1f}s")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Access forbidden after {max_retries} attempts for {url}")
                    raise requests.RequestException(f"Access forbidden: HTTP 403")
            
            # Success
            resp.raise_for_status()
            return resp
            
        except requests.RequestException as exc:
            if attempt + 1 < max_retries:
                wait_time = (2 ** attempt) + random.uniform(0.5, 1.5)
                logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {exc}, retrying after {wait_time:.1f}s")
                time.sleep(wait_time)
            else:
                logger.error(f"Request failed after {max_retries} attempts: {exc}")
                raise


def http_get(url, timeout=15, headers=None, delay=None, **kwargs):
    """Shared HTTP GET helper using one session for connection reuse.

    Supports optional delays between remote requests to avoid rate limiting
    and reduce anti-scraping detection.
    """
    return http_get_with_retry(url, timeout, headers, delay, max_retries=3, **kwargs)

    raise RuntimeError(f'HTTP GET failed for {url} after {attempts} attempts')

# Try to load an encrypted RadioReference API key (optional)
RR_API_KEY = None
# Optional hardcoded API credentials.
# Set these if you want the API key/passphrase embedded directly in the source.
# NOTE: this is only recommended for trusted local deployments.
HARDCODED_RR_API_KEY = None
HARDCODED_RR_API_PASS = None
try:
    from rr_api import load_api_key
    enc_path = os.path.join(os.path.dirname(__file__), 'rr_api.enc')
    passphrase = os.environ.get('RR_API_PASS') or HARDCODED_RR_API_PASS
    if passphrase and os.path.exists(enc_path):
        try:
            RR_API_KEY = load_api_key(passphrase, enc_path)
        except Exception:
            RR_API_KEY = None
except Exception:
    RR_API_KEY = None

# Prefer an env-provided API key if present; otherwise use hardcoded key or load encrypted key if possible.
try:
    key_candidate = os.environ.get('RR_API_KEY') or HARDCODED_RR_API_KEY
    if key_candidate:
        RR_API_KEY = key_candidate
    else:
        import rr_api as _rr_api
        enc_path = os.path.join(os.path.dirname(__file__), 'rr_api.enc')
        passfile = os.path.abspath(os.path.join(os.path.dirname(__file__), '.rr_api_pass'))
        # If RR_API_PASS is set, hardcoded pass is provided, or passfile exists, try to load
        passphrase = os.environ.get('RR_API_PASS') or HARDCODED_RR_API_PASS
        if passphrase and os.path.exists(enc_path):
            try:
                RR_API_KEY = _rr_api.load_api_key(passphrase, enc_path)
            except Exception:
                RR_API_KEY = None
        else:
            # If enc exists and we can read passfile, try that as last resort
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
            # No built-in key is bundled; users must supply their own via RR_API_KEY,
            # RR_API_PASS, HARDCODED_RR_API_KEY, HARDCODED_RR_API_PASS, or through the Preferences dialog.
except Exception:
    pass

# NOAA weather channels are provided in csv_files/US NOAA Weather Alert.csv
# The United States has 10 standard NOAA weather radio channels.
NOAA_CHANNEL_LIMIT = 10
NOAA_CSV = os.path.join(os.path.dirname(__file__), 'csv_files', 'US NOAA Weather Alert.csv')
NOAA_FREQS = []
try:
    import csv as _csv
    with open(NOAA_CSV, newline='', encoding='utf-8') as _fh:
        reader = _csv.DictReader(_fh)
        for row in reader:
            if len(NOAA_FREQS) >= NOAA_CHANNEL_LIMIT:
                break
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

# Local calling frequencies for HAM bands
LOCAL_CALLING_FREQS = [
    # 2m calling frequencies
    ('National Simplex Calling Frequency', '146.520', '', ''),
    ('Regional Calling 1', '146.550', '', ''),
    ('Regional Calling 2', '146.580', '', ''),
    # 70cm calling frequencies  
    ('National UHF Simplex', '446.000', '', ''),
    ('UHF Calling 1', '446.025', '', ''),
    ('UHF Calling 2', '446.050', '', ''),
    # 1.25m calling frequency
    ('220 MHz Calling', '223.500', '', ''),
]
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
    "Cook County, Illinois": "https://www.radioreference.com/db/browse/ctid/606",
}

# Band definitions for GUI selection and filtering (ranges in MHz)
BAND_RANGES = {
    '10m': [(28.0, 29.7)],
    '6m': [(50.0, 54.0)],
    '2m': [(144.0, 148.0)],
    '1.25m': [(222.0, 225.0)],
    '70cm': [(420.0, 450.0)],
    '33cm': [(902.0, 928.0)],
    '23cm': [(1240.0, 1300.0)],
    'NOAA': [(162.4, 162.55)],
    'MURS': [(151.82, 154.6)],
    'FRS/GMRS': [(462.0, 467.0)],
    # Emergency: heuristic ranges covering common public-safety analog bands
    # This includes police, citywide, EMS, fire, and similar dispatch channels.
    # Ranges adjusted to exclude ham radio bands (2m: 144-148, 70cm: 420-450)
    'Emergency': [
        (30.0, 50.0),    # Low VHF (some legacy)
        (138.0, 144.0),  # VHF high-band below 2m ham band
        (148.0, 162.399),  # VHF high-band above 2m ham band (excluding NOAA)
        (162.551, 174.0),  # VHF high-band above NOAA weather band
        (380.0, 420.0),  # UHF public safety below 70cm ham band
        (450.0, 470.0),  # UHF public safety above 70cm ham band
        (700.0, 900.0),  # 700/800 MHz public-safety ranges
    ],
}

PAGE_BAND_GROUPS = [
    ('Zip Code', []),
    ('Ham-SSB/AM', ['10m', '6m', '2m', '1.25m', '70cm', '33cm', '23cm']),
    ('MURS', ['MURS']),
    ('GMRS/FRS', ['FRS/GMRS']),
    ('Emergency', ['Emergency']),
]

# Group HAM bands together for better organization
HAM_BANDS = ['10m', '6m', '2m', '1.25m', '70cm', '33cm', '23cm']

DEFAULT_BAND_PROFILES = {
    'Emergency Comms': {
        'bands': ['70cm', '1.25m', '2m', 'Emergency', 'NOAA'],
        'order': ['70cm', '1.25m', '2m', 'Emergency', 'NOAA'],
        'emergency_types': ['Police', 'Fire', 'EMS', 'Citywide'],
        'scanner_mode': True,
    },
    'Traveler': {
        'bands': ['70cm', '1.25m', '2m', 'Emergency', 'NOAA'],
        'order': ['70cm', '1.25m', '2m', 'Emergency', 'NOAA'],
        'emergency_types': ['Police', 'Fire', 'EMS', 'Citywide'],
        'scanner_mode': True,
    },
    'HamScan': {
        'bands': ['70cm', '1.25m', '2m'],
        'order': ['70cm', '1.25m', '2m'],
        'emergency_types': [],
        'scanner_mode': True,
    },
}

EMERGENCY_TYPE_KEYWORDS = {
    'Fire': ['fireground', 'fire ground', 'fire-tac', 'fire dispatch', 'engine', 'fire', 'fd'],
    'EMS': ['ems-tac', 'ems:', 'ambulance', 'medical', 'emt', 'ems'],
    'Police': ['sheriff', 'law enforcement', 'police', 'pd', 'law', 'tac', 'tactical'],
    'Citywide': ['citywide', 'city-wide', 'city wide', 'c/w', 'cw'],
}

def emergency_row_type(row):
    text = ' '.join(filter(None, [
        str(row.get('Name', '')),
        str(row.get('Comment', '')),
        str(row.get('RawText', '')),
    ])).lower()
    for et, keywords in EMERGENCY_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return et
    return None


def _row_score(row, model_info=None):
    """Score function for ranking export rows by completeness and quality."""
    score = 0
    for field in ('Name', 'Comment', 'Tone', 'rToneFreq', 'cToneFreq', 'DtcsCode', 'Duplex', 'Offset'):
        if row.get(field):
            score += 1
    score += len(str(row.get('Name','')))
    score += len(str(row.get('Comment','')))
    
    # Bonus for radio model frequency compatibility
    if model_info and 'frequency_ranges' in model_info:
        freq = row.get('Frequency')
        if freq:
            try:
                freq_float = float(freq)
                for low, high in model_info['frequency_ranges']:
                    if low <= freq_float <= high:
                        score += 50  # Significant bonus for compatible frequencies
                        break
            except (ValueError, TypeError):
                pass
    
    return score

def select_zip_rows_with_fair_limit(zip_rows, remaining_slots, zip_order=None, prioritize_quality=False, model_info=None):
    """Select rows across ZIPs using proportional allocation by available rows."""
    if not zip_rows or remaining_slots <= 0:
        return []
    if prioritize_quality:
        for zip_code, rows in zip_rows.items():
            zip_rows[zip_code] = sorted(rows, key=lambda row: _row_score(row, model_info), reverse=True)
    zip_counts = {zip_code: len(rows) for zip_code, rows in zip_rows.items()}
    total_rows = sum(zip_counts.values())
    if total_rows <= 0:
        return []

    if zip_order:
        order_index = {zip_code: idx for idx, zip_code in enumerate(zip_order)}
        sorted_zips = sorted(zip_rows.keys(), key=lambda z: (zip_counts[z], order_index.get(z, 999)))
    else:
        sorted_zips = sorted(zip_rows.keys(), key=lambda z: (zip_counts[z], z))

    zip_targets = {}
    fractions = []
    for zip_code in sorted_zips:
        exact = remaining_slots * zip_counts[zip_code] / total_rows
        base = int(exact)
        zip_targets[zip_code] = base
        fractions.append((exact - base, zip_code))

    assigned = sum(zip_targets.values())
    diff = remaining_slots - assigned
    if diff > 0:
        fractions.sort(key=lambda t: (-t[0], zip_counts[t[1]], t[1]))
        for _, zip_code in fractions[:diff]:
            zip_targets[zip_code] += 1
    elif diff < 0:
        fractions.sort(key=lambda t: (t[0], -zip_counts[t[1]], t[1]))
        for _, zip_code in fractions[: -diff]:
            zip_targets[zip_code] -= 1

    selected = []
    overflow = []
    for zip_code in sorted_zips:
        rows = zip_rows.get(zip_code, [])
        target = min(zip_targets.get(zip_code, 0), len(rows))
        selected.extend(rows[:target])
        for overflow_row in rows[target:]:
            overflow.append((zip_counts[zip_code], zip_code, overflow_row))

    needed = remaining_slots - len(selected)
    if needed > 0:
        overflow.sort(key=lambda item: (-item[0], item[1]))
        for _, _, extra_row in overflow[:needed]:
            selected.append(extra_row)
    return selected


def is_analog_emergency_channel(name, row_text='', comment='', model_obj=None):
    """Return True if the emergency row is usable by an analog-only radio."""
    if model_obj and (model_obj.get('supports_p25') or model_obj.get('supports_digital_mode')):
        return True
    combined = ' '.join(filter(None, [row_text or '', name or '', comment or ''])).lower()
    if not combined:
        return True
    if re.search(r'\b(?:p25(?:e)?|project 25|edacs|dmr|nxdn|tdma|trunk|trunked|talkgroup|tg|starcom21|phase ii|digital|simulcast)\b', combined):
        return False
    return True

# Radio Model Definitions with Supported Features
RADIO_MODELS = {
    'Generic': {
        'name': 'Generic Radio (Default)',
        'supports_tone': True,
        'supports_p25': False,
        'supports_edacs': False,
        'supports_dstar': False,
        'supports_dtcs': True,
        'supports_duplex': True,
        'supports_offset': True,
        'supports_step': True,
        'supports_mode': True,
        'supports_skip': True,
    'supports_1_25': False,
        'max_channels': 1000,
        'tone_frequencies': True,
        'frequency_ranges': [(136.0, 174.0), (222.0, 225.0), (400.0, 520.0), (700.0, 900.0)],
        'description': 'Compatible with most CHIRP-supported radios'
    },

    'Baofeng_UV82': {
        'name': 'Baofeng UV-82',
        'supports_tone': True,
        'supports_p25': False,
        'supports_edacs': False,
        'supports_dstar': False,
        'supports_dtcs': True,
        'supports_duplex': True,
        'supports_offset': True,
        'supports_step': True,
        'supports_mode': True,
        'supports_skip': True,
        'max_channels': 125,
        'supports_1_25': False,
        'tone_frequencies': True,
        'frequency_ranges': [(136.0, 174.0), (400.0, 520.0)],
        'description': 'Rugged dual-band UHF/VHF handheld. Includes UV-82LP and UV-82X variants.'
    },

    'Baofeng_UV5R': {
        'name': 'Baofeng UV-5R',
        'supports_tone': True,
        'supports_p25': False,
        'supports_edacs': False,
        'supports_dstar': False,
        'supports_dtcs': True,
        'supports_duplex': True,
        'supports_offset': True,
        'supports_step': True,
        'supports_mode': True,
        'supports_skip': True,
        'max_channels': 125,
        'supports_1_25': False,
        'tone_frequencies': True,
        'frequency_ranges': [(136.0, 174.0), (400.0, 520.0)],
        'description': 'Popular budget dual-band UHF/VHF handheld. Includes UV-5R Mini and UV-5R Plus variants.'
    },

    'Baofeng_UV5R_Mini': {
        'name': 'Baofeng UV-5R Mini',
        'supports_tone': True,
        'supports_p25': False,
        'supports_edacs': False,
        'supports_dstar': False,
        'supports_dtcs': True,
        'supports_duplex': True,
        'supports_offset': True,
        'supports_step': True,
        'supports_mode': True,
        'supports_skip': True,
        'max_channels': 125,
        'supports_1_25': False,
        'tone_frequencies': True,
        'frequency_ranges': [(136.0, 174.0), (400.0, 520.0)],
        'description': 'UV-5R Mini variant with the same core features and compatibility as UV-5R.'
    },

    'Baofeng_UV5R_Plus': {
        'name': 'Baofeng UV-5R Plus',
        'supports_tone': True,
        'supports_p25': False,
        'supports_edacs': False,
        'supports_dstar': False,
        'supports_dtcs': True,
        'supports_duplex': True,
        'supports_offset': True,
        'supports_step': True,
        'supports_mode': True,
        'supports_skip': True,
        'max_channels': 125,
        'supports_1_25': False,
        'tone_frequencies': True,
        'frequency_ranges': [(136.0, 174.0), (400.0, 520.0)],
        'description': 'UV-5R Plus variant with expanded firmware compatibility and same channel support.'
    },

    'Baofeng_UV82': {
        'name': 'Baofeng UV-82',
        'supports_tone': True,
        'supports_p25': False,
        'supports_edacs': False,
        'supports_dstar': False,
        'supports_dtcs': True,
        'supports_duplex': True,
        'supports_offset': True,
        'supports_step': True,
        'supports_mode': True,
        'supports_skip': True,
        'supports_comment': True,
        'max_channels': 125,
        'supports_1_25': False,
        'tone_frequencies': True,
        'frequency_ranges': [(136.0, 174.0), (400.0, 520.0)],
        'description': 'Rugged dual-band UHF/VHF handheld. Includes UV-82LP and UV-82X variants.'
    },

    'Baofeng_UV82_LP': {
        'name': 'Baofeng UV-82LP',
        'supports_tone': True,
        'supports_p25': False,
        'supports_edacs': False,
        'supports_dstar': False,
        'supports_dtcs': True,
        'supports_duplex': True,
        'supports_offset': True,
        'supports_step': True,
        'supports_mode': True,
        'supports_skip': True,
        'supports_comment': True,
        'max_channels': 125,
        'supports_1_25': False,
        'tone_frequencies': True,
        'frequency_ranges': [(136.0, 174.0), (400.0, 520.0)],
        'description': 'Low-power UV-82LP variant with the same feature set and compatibility as UV-82.'
    },
    'Motorola': {
        'name': 'Motorola (Professional)',
        'supports_tone': True,
        'supports_p25': True,
        'supports_edacs': False,
        'supports_dstar': False,
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
        'supports_1_25': False,
        'tone_frequencies': True,
        'frequency_ranges': [(136.0, 174.0), (380.0, 520.0), (700.0, 900.0)],
        'description': 'Professional grade digital/analog radio'
    },
    'Kenwood': {
        'name': 'Kenwood (VHF/UHF)',
        'supports_tone': True,
        'supports_p25': True,
        'supports_edacs': False,
        'supports_dstar': False,
        'supports_dtcs': True,
        'supports_duplex': True,
        'supports_offset': True,
        'supports_step': True,
        'supports_mode': True,
        'supports_skip': True,
        'supports_comment': True,
        'max_channels': 1000,
        'supports_1_25': True,
        'tone_frequencies': True,
        'frequency_ranges': [(136.0, 174.0), (222.0, 225.0), (400.0, 520.0)],
        'description': 'Kenwood mobile/portable radios'
    },
    'Motorola_APX': {
        'name': 'Motorola APX Series',
        'supports_tone': True,
        'supports_p25': True,
        'supports_edacs': False,
        'supports_dstar': False,
        'supports_dtcs': True,
        'supports_duplex': True,
        'supports_offset': True,
        'supports_step': True,
        'supports_mode': True,
        'supports_skip': True,
        'supports_comment': True,
        'supports_digital_mode': True,
        'max_channels': 5000,
        'supports_1_25': False,
        'tone_frequencies': True,
        'frequency_ranges': [(136.0, 174.0), (380.0, 520.0), (700.0, 900.0)],
        'description': 'Professional P25-capable Motorola radios (APX series)'
    },
    'Icom_P25': {
        'name': 'Icom P25-capable',
        'supports_tone': True,
        'supports_p25': True,
        'supports_edacs': False,
        'supports_dstar': False,
        'supports_dtcs': True,
        'supports_duplex': True,
        'supports_offset': True,
        'supports_step': True,
        'supports_mode': True,
        'supports_skip': True,
        'supports_comment': True,
        'supports_digital_mode': True,
        'max_channels': 5000,
        'supports_1_25': True,
        'tone_frequencies': True,
        'frequency_ranges': [(136.0, 174.0), (222.0, 225.0), (400.0, 520.0), (700.0, 900.0)],
        'description': 'Icom radios with P25 capability'
    },
    'Icom_ID51': {
        'name': 'Icom ID-51A PLUS2',
        'supports_tone': True,
        'supports_p25': False,
        'supports_edacs': False,
        'supports_dstar': True,
        'supports_dtcs': True,
        'supports_duplex': True,
        'supports_offset': True,
        'supports_step': True,
        'supports_mode': True,
        'supports_skip': True,
        'supports_comment': True,
        'supports_digital_mode': True,
        'max_channels': 500,
        'supports_1_25': False,
        'tone_frequencies': True,
        'frequency_ranges': [(136.0, 174.0), (400.0, 470.0)],
        'description': 'D-STAR dual-band handheld with GPS and Bluetooth'
    },
    'Icom_ID5100': {
        'name': 'Icom ID-5100E',
        'supports_tone': True,
        'supports_p25': False,
        'supports_edacs': False,
        'supports_dstar': True,
        'supports_dtcs': True,
        'supports_duplex': True,
        'supports_offset': True,
        'supports_step': True,
        'supports_mode': True,
        'supports_skip': True,
        'supports_comment': True,
        'supports_digital_mode': True,
        'max_channels': 1000,
        'supports_1_25': False,
        'tone_frequencies': True,
        'frequency_ranges': [(136.0, 174.0), (400.0, 470.0)],
        'description': 'D-STAR dual-band mobile with touchscreen and GPS'
    },
    'Yaesu_FTM400': {
        'name': 'Yaesu FTM-400DR',
        'supports_tone': True,
        'supports_p25': False,
        'supports_edacs': False,
        'supports_dstar': False,
        'supports_dtcs': True,
        'supports_duplex': True,
        'supports_offset': True,
        'supports_step': True,
        'supports_mode': True,
        'supports_skip': True,
        'supports_comment': True,
        'supports_digital_mode': True,
        'max_channels': 500,
        'supports_1_25': False,
        'tone_frequencies': True,
        'frequency_ranges': [(136.0, 174.0), (400.0, 470.0)],
        'description': 'System Fusion digital mobile radio'
    },
    'Yaesu_FTM100': {
        'name': 'Yaesu FTM-100DR',
        'supports_tone': True,
        'supports_p25': False,
        'supports_edacs': False,
        'supports_dstar': False,
        'supports_dtcs': True,
        'supports_duplex': True,
        'supports_offset': True,
        'supports_step': True,
        'supports_mode': True,
        'supports_skip': True,
        'supports_comment': True,
        'supports_digital_mode': True,
        'max_channels': 500,
        'supports_1_25': False,
        'tone_frequencies': True,
        'frequency_ranges': [(136.0, 174.0), (400.0, 470.0)],
        'description': 'System Fusion digital compact mobile radio'
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

def model_supports_frequency(model_obj, freq):
    try:
        fv = float(freq)
    except Exception:
        return False
    ranges = model_obj.get('frequency_ranges')
    if not ranges:
        return True
    return any(lo <= fv <= hi for lo, hi in ranges)

def scrape_rr(url):
    """Fetch `url` and return parsed frequency rows via parse_rr_html."""
    resp = http_get(url, timeout=15)
    return parse_rr_html(resp.text)


def parse_rr_html(html_text):
    """Parse RadioReference HTML (string) and return list of tuples like scrape_rr."""
    soup = BeautifulSoup(html_text, "html.parser")
    out = []
    for table in soup.select("table.rrdbTable"):
        rows = table.select("tbody tr")
        if not rows:
            rows = [tr for tr in table.select("tr") if tr.find_all("td")]
        for tr in rows:
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
            out.append((name, f, tone, duplex_hint, offset_hint, other_texts))
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
    result = scrape_rr(url)
    if not result:
        ctid_alt = re.sub(r'(/db/browse/ctid/\d+)(?:/ham)?/?$', r'\1', url, flags=re.I)
        if ctid_alt and ctid_alt != url:
            result = scrape_rr(ctid_alt)
    return result


def get_rr_counterpart_page(url, target_page):
    """Return a `ham` or `emergency` variant page URL for a RadioReference CTID or ZIP page."""
    if not url:
        return url
    if re.search(r'/(ham|emergency)/?$', url, flags=re.I):
        return re.sub(r'/(ham|emergency)/?$', f'/{target_page}', url, flags=re.I)
    return url


BAND_TOKEN_ALIASES = {
    '2M': '2m',
    '70CM': '70cm',
    '1.25M': '1.25m',
    '125M': '1.25m',
    'NOAA': 'NOAA',
    'EMERGENCY': 'Emergency',
    'MURS': 'MURS',
    'FRS': 'FRS/GMRS',
    'GMRS': 'FRS/GMRS',
    'FRSGMRS': 'FRS/GMRS',
}


def normalize_band_token(token):
    token = token or ''
    normalized = re.sub(r'[^A-Z0-9]', '', token.strip().upper())
    return normalized


def canonical_band_name(token):
    return BAND_TOKEN_ALIASES.get(normalize_band_token(token))


def is_band_token(token):
    return canonical_band_name(token) is not None


def parse_input_tokens(text):
    if not text:
        return []
    return [tok for tok in re.split(r"[\s,;:-]+", text.strip()) if tok]


def extract_band_tokens(text):
    bands = []
    for tok in parse_input_tokens(text):
        band = canonical_band_name(tok)
        if band and band not in bands:
            bands.append(band)
    return bands

SPECIAL_BAND_TOKEN_GROUPS = {
    'HAM': ['2m', '70cm', '1.25m'],
    'REPEATER': ['2m', '70cm', '1.25m'],
}

def expand_band_tokens(tokens):
    bands = []
    for tok in tokens:
        normalized = normalize_band_token(tok)
        if normalized in SPECIAL_BAND_TOKEN_GROUPS:
            for band in SPECIAL_BAND_TOKEN_GROUPS[normalized]:
                if band not in bands:
                    bands.append(band)
            continue
        band = canonical_band_name(tok)
        if band and band not in bands:
            bands.append(band)
    return bands


def build_radioreference_pages(tokens, rr_index=None):
    return {label: url for label, url, _ in build_radioreference_page_entries(tokens, rr_index)}


def build_radioreference_page_entries(tokens, rr_index=None):
    entries = []
    for tok in tokens:
        if tok.startswith('http://') or tok.startswith('https://'):
            entries.append((tok, tok, None))
            continue
        if re.fullmatch(r'^\d{5}$', tok):
            zip_code = tok
            label = f'ZIP {tok}'
            url = f'https://www.radioreference.com/db/search/?zip={tok}'
            if rr_index is not None:
                try:
                    pr = http_get(f'http://api.zippopotam.us/us/{tok}', timeout=6)
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
                                        label = f"{county}, {state} ({tok})"
                                        url = f'https://www.radioreference.com/db/browse/ctid/{ctid}/ham'
                    elif pr.status_code == 404:
                        # ZIP not found in zippopotam, silently continue with fallback
                        pass
                except Exception as e:
                    # Silently handle API errors - fallback to basic ZIP search
                    pass
            entries.append((label, url, zip_code))
            continue
    return entries


def get_pages_from_user():
    """Get a dict of {label: url} from the user.

    Supports:
    - GUI prompt (Tk) when a desktop session is available
    - Terminal prompt fallback

    Input may be comma/space separated tokens. Tokens that look like URLs
    (start with http) are used directly. Otherwise tokens are treated as
    US ZIP codes and a Radioreference browse-by-zip URL is constructed.

    Band names are not page selectors; they should be chosen separately in the GUI.
    """
    prompt_text = (
        "Enter ZIP codes or Radioreference URLs (comma, hyphen, or space separated).\n"
        "Examples: 60601, 1319, 60626-49626-49677, https://www.radioreference.com/db/browse/ctid/606\n"
        "Bands: 2m, 70cm, 1.25m, NOAA, Emergency can also be typed and will be treated as band selections."
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

    tokens = parse_input_tokens(input_str)
    pages = {}
    bands = []
    for t in tokens:
        if is_band_token(t):
            band = canonical_band_name(t)
            if band and band not in bands:
                bands.append(band)
            continue
        if t.startswith("http://") or t.startswith("https://"):
            label = t
            pages[label] = t
            continue
        if re.fullmatch(r'\d{5}', t):
            url = f"https://www.radioreference.com/db/search/?zip={t}"
            pages[f"ZIP {t}"] = url
            continue
        # unsupported token is ignored
    return pages, bands


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


def get_remote_radioref_raw_url():
    """Derive a raw GitHub URL for radioref.csv from the repository's Git remote."""
    repo_dir = os.path.dirname(__file__)
    git_dir = os.path.join(repo_dir, '.git')
    if not os.path.isdir(git_dir):
        return None
    try:
        remote = subprocess.check_output(
            ['git', 'config', '--get', 'remote.origin.url'],
            cwd=repo_dir,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None

    if not remote:
        return None

    m = re.match(r'(?:git@github\.com:|ssh://git@github\.com/)([^/]+)/([^/]+?)(?:\.git)?$', remote)
    if m:
        owner, repo = m.group(1), m.group(2)
    else:
        m = re.match(r'https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?$', remote)
        if m:
            owner, repo = m.group(1), m.group(2)
        else:
            return None
    return f'https://raw.githubusercontent.com/{owner}/{repo}/main/radioref.csv'


def refresh_rr_index():
    """Attempt to refresh the local radioref.csv from a GitHub raw repository URL."""
    csv_path = os.path.join(os.path.dirname(__file__), 'radioref.csv')
    remote_url = get_remote_radioref_raw_url()
    if not remote_url:
        return False
    try:
        resp = http_get(remote_url, timeout=20)
        if resp.status_code == 200 and resp.content:
            try:
                with open(csv_path, 'wb') as rf:
                    rf.write(resp.content)
                return True
            except Exception:
                return False
    except Exception:
        return False
    return False


def load_rr_index(force_refresh=False):
    """Load RadioReference CTID index from radioref.csv.

    Returns mapping from normalized 'County, State' or 'City, State' lowercased
    labels to CTID IDs.
    """
    import csv

    csv_path = os.path.join(os.path.dirname(__file__), 'radioref.csv')
    settings = load_persistent_settings()
    offline_cache_enabled = bool(settings.get('offline_cache', 0))
    should_refresh = force_refresh or (not os.path.exists(csv_path) and not offline_cache_enabled)
    if should_refresh:
        refreshed = refresh_rr_index()
        if force_refresh and not refreshed:
            message = 'Could not refresh radioref.csv from the configured repository. '
            message += 'Using local data if present.'
            print(message)

    index = {}
    try:
        with open(csv_path, newline='', encoding='utf-8') as rf:
            reader = csv.DictReader(rf)
            for row in reader:
                title = row.get('location_title', '').strip()
                t = re.sub(r'\s*Amateur Radio$', '', title)
                t = re.sub(r'\s*\([^)]*\)\s*$', '', t).strip()
                if ',' in t and ('County' in t or 'City' in t):
                    index[t.lower()] = row.get('id')
    except Exception:
        pass
    return index


def get_county_from_zip(zip_code):
    """Given a ZIP code, fetch the RR zip page and try to find the county page link (ctid).

    Returns (label, url) or (None, zip_page_url) on fallback.
    """
    zip_url = f"https://www.radioreference.com/db/search/?zip={zip_code}"
    try:
        r = http_get(zip_url, timeout=10)
        if re.search(r'/db/browse/ctid/\d+', r.url):
            soup = BeautifulSoup(r.text, 'html.parser')
            title = None
            h2 = soup.select_one('h2')
            if h2 and h2.text.strip():
                title = h2.text.strip()
            elif soup.title and soup.title.text:
                title = soup.title.text.strip()
            return (title or f'ZIP {zip_code}', r.url)
    except Exception:
        pass

    # fallback: try to resolve county via zippopotam.us -> reverse geocode -> local index -> search RR
    try:
        response = http_get(f'http://api.zippopotam.us/us/{zip_code}', timeout=8)
        if response.status_code == 200:
            place = response.json()
            places = place.get('places', [])
        else:
            # ZIP not found, skip this fallback
            places = []
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
                    key = f"{county}, {state_name}".lower()
                    rr_index = load_rr_index()
                    ctid = rr_index.get(key)
                    if ctid:
                        return (f"{county}, {state_name}", f'https://www.radioreference.com/db/browse/ctid/{ctid}/ham')
                    # search RadioReference for county page if local index does not have it
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
    """Return's U.S. state name for a ZIP code."""
    try:
        r = http_get(f'http://api.zippopotam.us/us/{zipcode}', timeout=8)
        if r.status_code == 200:
            pj = r.json()
            places = pj.get('places', [])
            if not places:
                return None
            return places[0].get('state')
        else:
            # ZIP not found in API - check if it's a valid US ZIP format
            if len(zipcode) == 5 and zipcode.isdigit():
                # Valid ZIP format but not found, return None for fallback
                return None
            else:
                # Invalid ZIP format
                return None
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


# New frequency source implementations with safety mechanisms

# Enhanced logging for debugging
import logging
import hashlib
import json
import os
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Simple caching system for frequently accessed data
CACHE_DIR = os.path.expanduser('~/.freqfinder_cache')
CACHE_EXPIRY_HOURS = 24  # Cache expires after 24 hours

def get_cache_key(source, **kwargs):
    """Generate cache key for source and parameters."""
    key_parts = [source]
    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}={v}")
    return hashlib.md5('|'.join(key_parts).encode()).hexdigest()

def get_cached_data(cache_key):
    """Retrieve cached data if available and not expired."""
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    
    if not os.path.exists(cache_file):
        return None
        
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
            
        # Check if cache is expired
        cache_time = datetime.fromisoformat(cache_data.get('timestamp', '1970-01-01T00:00:00'))
        if datetime.now() - cache_time > timedelta(hours=CACHE_EXPIRY_HOURS):
            logger.debug(f"Cache expired for {cache_key}")
            os.remove(cache_file)
            return None
            
        logger.info(f"Using cached data for {cache_key}")
        return cache_data.get('data', [])
    except Exception as e:
        logger.error(f"Cache read error: {e}")
        return None

def cache_data(cache_key, data):
    """Store data in cache with timestamp."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        
        cache_data = {
            'timestamp': datetime.now().isoformat(),
            'data': data
        }
        
        cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2)
            
        logger.info(f"Cached {len(data)} items for {cache_key}")
    except Exception as e:
        logger.error(f"Cache write error: {e}")

def scrape_repeaterbook(zipcode=None, state=None, callsign=None):
    """Scrape repeater data from RepeaterBook.com with safety measures.
    
    Args:
        zipcode: 5-digit ZIP code for location-based search
        state: 2-letter state code for state-wide search  
        callsign: Callsign for specific repeater search
        
    Returns:
        List of tuples (name, frequency, tone, duplex_hint, offset_hint, other_texts)
    """
    import random
    import time
    import re
    
    # Enhanced safety headers for RepeaterBook
    rb_headers = {
        **DEFAULT_HEADERS,
        'Referer': 'https://www.repeaterbook.com/',
        'Cache-Control': 'max-age=0',
        'X-Requested-With': 'XMLHttpRequest',
    }
    
    # Source-specific rate limiting
    SOURCE_DELAYS = {
        'repeaterbook': 2.5,  # Conservative delay for RepeaterBook
        'qrz': 4.0,           # Longer delay for QRZ (more sensitive)
        'intercept_radio': 2.0,  # Moderate delay for InterceptRadio
        'radioreference': 1.0,   # Standard delay for RadioReference
    }
    
    results = []
    
    # Check cache first
    cache_key = None
    if callsign:
        cache_key = get_cache_key('repeaterbook', callsign=callsign)
    elif zipcode:
        cache_key = get_cache_key('repeaterbook', zipcode=zipcode)
    elif state:
        cache_key = get_cache_key('repeaterbook', state=state)
    else:
        cache_key = None
        
    if cache_key:
        cached_data = get_cached_data(cache_key)
        if cached_data:
            logger.info(f"Using cached RepeaterBook data for {cache_key}")
            return cached_data
    
    try:
        if callsign:
            # Search by callsign
            url = f"https://www.repeaterbook.com/global_repeaters/keyword.php?func=result&keyword={callsign}"
        elif zipcode:
            # Try multiple URL patterns for ZIP search
            urls_to_try = [
                f"https://www.repeaterbook.com/global_repeaters/keyword.php?func=result&keyword={zipcode}",
                f"https://www.repeaterbook.com/global_repeaters/zip.php?zip={zipcode}",
                f"https://www.repeaterbook.com/repeaters/state/IL?loc={zipcode}",  # Try state pattern
            ]
        elif state:
            # Search by state - try multiple URL patterns
            state_urls = [
                f"https://www.repeaterbook.com/global_repeaters/state.php?state={state}",
                f"https://www.repeaterbook.com/repeaters/state/{state}?loc=",  # Alternative pattern
            ]
            urls_to_try = state_urls
        else:
            return results
            
        # Try each URL until we get results
        urls_to_test = urls_to_try if zipcode else [url]
        
        for test_url in urls_to_test:
            # Add source-specific delay to avoid detection
            import random
            source_delay = SOURCE_DELAYS.get('repeaterbook', 2.0)
            time.sleep(random.uniform(source_delay * 0.8, source_delay * 1.2))
            
            try:
                resp = http_get(test_url, headers=rb_headers, timeout=20, delay=2.0)
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # Look for any data in the response
                text_content = soup.get_text()
                
                # Check if we have meaningful results
                if 'No results' in text_content or len(text_content) < 500:
                    continue
                    
                # Method 1: Look for structured data patterns
                # Pattern: Callsign Freq Tone Offset Location
                lines = text_content.split('\n')
                for line in lines:
                    line = line.strip()
                    if not line or len(line) < 10:
                        continue
                        
                    # Look for frequency patterns with repeater context
                    freq_match = re.search(r'(\d{3}\.\d{3})', line)
                    if not freq_match:
                        continue
                        
                    freq_str = freq_match.group(1)
                    try:
                        freq = float(freq_str)
                        if not valid_freq(freq):
                            continue
                    except ValueError:
                        continue
                        
                    # Extract callsign from the same line or nearby lines
                    callsign_match = re.search(r'([A-Z0-9]{1,2}[A-Z][A-Z0-9]{1,4})', line)
                    if callsign_match:
                        name = callsign_match.group(1)
                    else:
                        # Look in nearby lines
                        name = f'RB_{freq_str}'
                        
                    # Extract tone if present
                    tone_match = re.search(r'(\d{2,3}\.\d+)', line)
                    tone = tone_match.group(1) if tone_match and tone_match.group(1) != freq_str else ''
                    
                    # Parse duplex
                    duplex_hint = None
                    if '+' in line:
                        duplex_hint = '+'
                    elif '-' in line:
                        duplex_hint = '-'
                        
                    results.append((name, freq, tone, duplex_hint, None, line))
                    
                if results:
                    break  # Found results, no need to try other URLs
                    
            except Exception as e:
                print(f"RepeaterBook URL {test_url} failed: {e}")
                continue
                
        # Method 2: Try to find JSON data or API endpoints
        if not results and zipcode:
            try:
                # Look for any JSON data in scripts
                scripts = soup.find_all('script')
                for script in scripts:
                    if script.string and 'repeaters' in script.string.lower():
                        # Try to extract JSON data
                        json_match = re.search(r'(\{.*\})', script.string)
                        if json_match:
                            try:
                                import json
                                data = json.loads(json_match.group(1))
                                # Parse JSON repeater data
                                if isinstance(data, dict) and 'repeaters' in data:
                                    for repeater in data['repeaters']:
                                        if isinstance(repeater, dict):
                                            freq = repeater.get('frequency')
                                            if freq and valid_freq(float(freq)):
                                                name = repeater.get('callsign', f'RB_{freq}')
                                                tone = repeater.get('tone', '')
                                                duplex = repeater.get('duplex')
                                                results.append((name, float(freq), tone, duplex, None, str(repeater)))
                            except:
                                pass
            except:
                pass
                    
        # Additional delay between requests
        time.sleep(random.uniform(2.0, 4.0))
        
    except Exception as e:
        logger.error(f"RepeaterBook scrape error: {e}")
        
    # Cache successful results
    if results:
        cache_data(cache_key, results)
        
    return results


def scrape_qrz_gridmapper(grid_square=None, callsign=None):
    """Scrape ham radio operator data from QRZ GridMapper with safety measures.
    
    Args:
        grid_square: Maidenhead grid square (e.g., 'EM13')
        callsign: Amateur radio callsign for lookup
        
    Returns:
        List of tuples (name, frequency, tone, duplex_hint, offset_hint, other_texts)
        Note: QRZ primarily provides operator info, not frequency data directly
    """
    import random
    import time
    import re
    
    # QRZ-specific headers
    qrz_headers = {
        **DEFAULT_HEADERS,
        'Referer': 'https://www.qrz.com/',
        'Origin': 'https://www.qrz.com',
    }
    
    # Source-specific delays for QRZ
    source_delays = {
        'repeaterbook': 2.5,  # Conservative delay for RepeaterBook
        'qrz': 4.0,           # Longer delay for QRZ (more sensitive)
        'intercept_radio': 2.0,  # Moderate delay for InterceptRadio
        'radioreference': 1.0,   # Standard delay for RadioReference
    }
    
    # Use source-specific delay for QRZ
    qrz_delay = source_delays.get('qrz', 4.0)
    
    results = []
    
    try:
        if callsign:
            # Direct callsign lookup
            url = f"https://www.qrz.com/db/{callsign}"
        elif grid_square:
            # Grid square search
            url = f"https://www.qrz.com/gridmapper?grid={grid_square}"
        else:
            return results
            
        # Use source-specific delay for QRZ
        time.sleep(random.uniform(qrz_delay * 0.8, qrz_delay * 1.2))
        
        resp = http_get(url, headers=qrz_headers, timeout=20, delay=3.0)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Check if login is required
        text_content = soup.get_text().lower()
        if 'login' in text_content and 'register' in text_content:
            # QRZ requires login for detailed data
            if callsign:
                results.append((callsign, None, None, None, None, f"QRZ requires login for detailed {callsign} data"))
            else:
                results.append(("QRZ_Search", None, None, None, None, f"QRZ requires login for grid square {grid_square} data"))
        else:
            # Try to extract public information
            if callsign:
                # Extract operator info from QRZ profile
                name_elem = soup.select_one("h1") or soup.select_one(".callsign")
                if name_elem:
                    name = name_elem.text.strip()
                    
                    # Look for any frequency-related information
                    freq_patterns = []
                    text = soup.get_text()
                    
                    # Try to find frequency mentions
                    freq_matches = re.findall(r'(\d{3}\.\d{3})', text)
                    for freq_str in freq_matches:
                        try:
                            freq = float(freq_str)
                            if valid_freq(freq):
                                freq_patterns.append(freq)
                        except ValueError:
                            continue
                    
                    if freq_patterns:
                        # Add frequency data if found
                        for freq in freq_patterns[:3]:  # Limit to avoid too many
                            results.append((name, freq, '', None, None, f"QRZ frequency data for {callsign}"))
                    else:
                        # Add basic operator info
                        results.append((name, None, None, None, None, f"QRZ operator lookup for {callsign} (no frequency data)"))
                        
            elif grid_square:
                # Grid square search - look for any operator data
                results.append(("QRZ_GridSearch", None, None, None, None, f"QRZ grid square search for {grid_square} (login required for details)"))
                
        # Extended delay for QRZ
        time.sleep(random.uniform(3.0, 5.0))
        
    except Exception as e:
        print(f"QRZ GridMapper scrape error: {e}")
        # Add error result
        if callsign:
            results.append((callsign, None, None, None, None, f"QRZ lookup failed for {callsign}: {str(e)}"))
        elif grid_square:
            results.append(("QRZ_GridSearch", None, None, None, None, f"QRZ grid search failed for {grid_square}: {str(e)}"))
        
    return results


def scrape_intercept_radio(zipcode):
    """Scrape ham radio frequencies from InterceptRadio.com with safety measures.
    
    Args:
        zipcode: 5-digit ZIP code
        
    Returns:
        List of tuples (name, frequency, tone, duplex_hint, offset_hint, other_texts)
    """
    import random
    import time
    import re
    
    # InterceptRadio specific headers
    ir_headers = {
        **DEFAULT_HEADERS,
        'Referer': 'http://www.interceptradio.com/',
    }
    
    results = []
    
    try:
        # Direct approach: Try the specific ZIP page first
        zip_url = f"http://www.interceptradio.com/ham.php?zip={zipcode}"
        
        # Use source-specific delay for InterceptRadio
        source_delays = {
            'repeaterbook': 2.5,  # Conservative delay for RepeaterBook
            'qrz': 4.0,           # Longer delay for QRZ (more sensitive)
            'intercept_radio': 2.0,  # Moderate delay for InterceptRadio
            'radioreference': 1.0,   # Standard delay for RadioReference
        }
        ir_delay = source_delays.get('intercept_radio', 2.0)
        time.sleep(random.uniform(ir_delay * 0.8, ir_delay * 1.2))
        
        try:
            resp = http_get(zip_url, headers=ir_headers, timeout=20, delay=2.0)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Parse the specific ZIP page
            text_content = soup.get_text()
            
            # Look for frequency patterns in the ZIP page
            lines = text_content.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line or len(line) < 10:
                    continue
                    
                # Try to extract frequency from the line
                freq_match = re.search(r'(\d{3}\.\d{3})', line)
                if not freq_match:
                    continue
                    
                try:
                    freq = float(freq_match.group(1))
                    if not valid_freq(freq):
                        continue
                        
                    # Extract callsign (usually at start of line)
                    callsign_match = re.match(r'^([A-Z0-9]{1,2}[A-Z][A-Z0-9]{1,4})', line)
                    name = callsign_match.group(1) if callsign_match else f'IR_{freq}'
                    
                    # Extract tone if present
                    tone_match = re.search(r'(\d{2,3}\.\d+)', line)
                    tone = tone_match.group(1) if tone_match and tone_match.group(1) != freq_match.group(1) else ''
                    
                    # Parse duplex hints
                    duplex_hint = None
                    offset_hint = None
                    if '+' in line:
                        duplex_hint = '+'
                    elif '-' in line:
                        duplex_hint = '-'
                        
                    results.append((name, freq, tone, duplex_hint, offset_hint, line))
                    
                except (ValueError, IndexError):
                    continue
                    
            if results:
                # Final delay
                time.sleep(random.uniform(2.0, 4.0))
                return results
                
        except Exception as e:
            print(f"Direct ZIP page failed: {e}")
            
        # Fallback: Use ZIP range approach
        zip_int = int(zipcode)
        
        # Determine which ZIP range page to use
        zip_ranges = [
            (0, 2894, 'ham00000-02894'),
            (2895, 5827, 'ham02895-05827'),
            (5828, 8805, 'ham05828-08805'),
            (8807, 12531, 'ham08807-12531'),
            (12533, 14873, 'ham12533-14873'),
            (14874, 17615, 'ham14874-17615'),
            (17623, 20777, 'ham17623-20777'),
            (20778, 23885, 'ham20778-23885'),
            (23888, 26845, 'ham23888-26845'),
            (26846, 29021, 'ham26846-29021'),
            (29025, 31012, 'ham29025-31012'),
            (31013, 33136, 'ham31013-33136'),
            (33137, 35291, 'ham33137-35291'),
            (35324, 38015, 'ham35324-38015'),
            (38016, 41083, 'ham38016-41083'),
            (41086, 44310, 'ham41086-44310'),
            (44311, 46765, 'ham44311-46765'),
            (46766, 48837, 'ham46766-48837'),
            (48838, 51342, 'ham48838-51342'),
            (51345, 54763, 'ham51345-54763'),
            (54766, 57259, 'ham54766-57259'),
            (57262, 60661, 'ham57262-60661'),
            (60666, 63051, 'ham60666-63051'),
            (63052, 66221, 'ham63052-66221'),
            (66223, 70302, 'ham66223-70302'),
            (70310, 72904, 'ham70310-72904'),
            (72906, 75551, 'ham72906-75551'),
            (75554, 77650, 'ham75554-77650'),
            (77651, 80402, 'ham77651-80402'),
            (80403, 84521, 'ham80403-84521'),
            (84523, 89040, 'ham84523-89040'),
            (89041, 92325, 'ham89041-92325'),
            (92327, 94949, 'ham92327-94949'),
            (94950, 97041, 'ham94950-97041'),
            (97042, 99012, 'ham97042-99012'),
            (99013, 99955, 'ham99013-99955'),
        ]
        
        range_file = None
        for start, end, filename in zip_ranges:
            if start <= zip_int <= end:
                range_file = filename
                break
                
        if not range_file:
            return results
            
        # Fetch the ZIP range page to find the ZIP link
        range_url = f"http://www.interceptradio.com/{range_file}.htm"
        
        time.sleep(random.uniform(1.5, 3.0))
        
        resp = http_get(range_url, headers=ir_headers, timeout=20, delay=2.0)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Find the link to the specific ZIP page
        zip_links = soup.find_all('a', href=re.compile(rf'ham\.php\?zip={zipcode}'))
        
        if zip_links:
            # Found the ZIP link, fetch that page
            zip_page_url = f"http://www.interceptradio.com/ham.php?zip={zipcode}"
            
            time.sleep(random.uniform(1.5, 3.0))
            
            resp = http_get(zip_page_url, headers=ir_headers, timeout=20, delay=2.0)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Parse the ZIP page
            text_content = soup.get_text()
            lines = text_content.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line or len(line) < 10:
                    continue
                    
                # Try to extract frequency from the line
                freq_match = re.search(r'(\d{3}\.\d{3})', line)
                if not freq_match:
                    continue
                    
                try:
                    freq = float(freq_match.group(1))
                    if not valid_freq(freq):
                        continue
                        
                    # Extract callsign (usually at start of line)
                    callsign_match = re.match(r'^([A-Z0-9]{1,2}[A-Z][A-Z0-9]{1,4})', line)
                    name = callsign_match.group(1) if callsign_match else f'IR_{freq}'
                    
                    # Extract tone if present
                    tone_match = re.search(r'(\d{2,3}\.\d+)', line)
                    tone = tone_match.group(1) if tone_match and tone_match.group(1) != freq_match.group(1) else ''
                    
                    # Parse duplex hints
                    duplex_hint = None
                    offset_hint = None
                    if '+' in line:
                        duplex_hint = '+'
                    elif '-' in line:
                        duplex_hint = '-'
                        
                    results.append((name, freq, tone, duplex_hint, offset_hint, line))
                    
                except (ValueError, IndexError):
                    continue
                    
        # Final delay
        time.sleep(random.uniform(2.0, 4.0))
        
    except Exception as e:
        print(f"InterceptRadio scrape error: {e}")
        
    return results


def validate_and_deduplicate_frequencies(results):
    """Validate and deduplicate frequency results from multiple sources.
    
    Args:
        results: List of tuples (name, frequency, tone, duplex_hint, offset_hint, other_texts)
        
    Returns:
        List of validated and deduplicated results
    """
    if not results:
        return []
        
    validated_results = []
    seen_frequencies = set()
    seen_callsigns = set()
    
    for result in results:
        if len(result) < 2:
            continue
            
        name, freq, tone, duplex_hint, offset_hint, other_texts = result
        
        # Skip if no frequency (QRZ operator lookup results)
        if freq is None:
            continue
            
        try:
            freq_float = float(freq)
        except (ValueError, TypeError):
            continue
            
        # Enhanced frequency validation for new sources
        if not valid_freq(freq_float):
            # Check if it's in known ham bands
            ham_bands = {
                (144.0, 148.0): '2m',
                (222.0, 225.0): '1.25m', 
                (420.0, 450.0): '70cm',
                (50.0, 54.0): '6m',
                (118.0, 136.0): '2m aircraft',
                (136.0, 174.0): '2m marine',
            }
            
            band_found = None
            for (low, high), band in ham_bands.items():
                if low <= freq_float <= high:
                    band_found = band
                    break
                    
            if band_found:
                logger.info(f"Valid ham band frequency {freq_float} ({band_found}) from {name}")
            else:
                logger.warning(f"Invalid frequency {freq_float} from {name}, not in ham bands")
                continue
            
        # Deduplicate by frequency and callsign
        freq_key = f"{freq_float:.3f}"
        callsign_key = name.upper().strip() if name else ''
        
        dup_key = (freq_key, callsign_key)
        if dup_key in seen_frequencies:
            logger.debug(f"Duplicate frequency/callsign {dup_key}, skipping")
            continue
            
        seen_frequencies.add(dup_key)
        seen_callsigns.add(callsign_key)
        
        # Validate and clean tone
        if tone:
            tone = str(tone).strip()
            # Remove invalid tone values
            if not tone or tone.lower() in ('none', 'n/a', ''):
                tone = ''
                
        # Clean and validate other fields
        clean_name = str(name).strip()[:50] if name else f'Unknown_{freq_float}'
        clean_other = str(other_texts).strip()[:200] if other_texts else ''
        
        validated_results.append((clean_name, freq_float, tone, duplex_hint, offset_hint, clean_other))
        
    logger.info(f"Validated {len(results)} results to {len(validated_results)} unique entries")
    return validated_results


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
    persistent_settings = load_persistent_settings()

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
    
    def write_export_csv(save_path, df):
        import csv as _csv
        out_cols = list(df.columns)
        with open(save_path, 'w', newline='', encoding='utf-8') as wf:
            writer = _csv.DictWriter(wf, fieldnames=['Location'] + out_cols)
            writer.writeheader()
            for row_tup in df.itertuples(index=True, name=None):
                rec = {'Location': row_tup[0]}
                for c, v in zip(out_cols, row_tup[1:]):
                    rec[c] = v
                writer.writerow(rec)

    def _normalize_export_filename(name_text):
        return re.sub(r'[^A-Za-z0-9]+', '_', str(name_text)).strip('_')

    def _compute_export_filename(source_name, model_name, bands):
        from datetime import datetime
        source_label = 'RadioRef' if str(source_name).lower().startswith('radioref') else 'RadioBrowser'
        model_label = _normalize_export_filename(model_name or 'Generic') or 'Generic'
        if bands:
            band_label = '-'.join(_normalize_export_filename(b) for b in bands if _normalize_export_filename(b))
        else:
            band_label = 'Bandplan'
        date_label = datetime.now().strftime('%Y%m%d')
        return f'FreqFinder_{model_label}_{source_label}_{band_label}_{date_label}.csv'

    def _get_default_export_filename(pages):
        selected_bands = []
        try:
            selected_bands = get_selected_band_order()
        except Exception:
            selected_bands = []
        source_name = preferences_data.get('selected_source').get() if preferences_data.get('selected_source') else 'RadioReference'
        model_raw = preferences_data.get('selected_model').get() if preferences_data.get('selected_model') else 'Generic'
        return _compute_export_filename(source_name, model_raw, selected_bands)

    def _get_zip_label(pages):
        if not isinstance(pages, dict):
            return None
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
                return '-'.join(unique_zips)
            return f"{unique_zips[0]}[{len(unique_zips)}]"
        return None

    def _get_default_export_filename_with_pages(pages):
        default_name = _get_default_export_filename(pages)
        zip_label = _get_zip_label(pages)
        if zip_label and zip_label != 'Bandplan':
            default_name = default_name.replace('_Bandplan_', f'_{zip_label}_')
        return default_name

    def _get_quick_export_default_filename():
        pages = exported_data.get('pages') or {}
        return _get_default_export_filename_with_pages(pages)

    def _get_preview_default_filename():
        pages = exported_data.get('pages') or {}
        name = _get_default_export_filename_with_pages(pages)
        return name.replace('.csv', '_Preview.csv')

    def _get_batch_export_filename(profile_name):
        source_name = preferences_data.get('selected_source').get() if preferences_data.get('selected_source') else 'RadioReference'
        model_raw = preferences_data.get('selected_model').get() if preferences_data.get('selected_model') else 'Generic'
        bands = get_selected_band_order() if callable(get_selected_band_order) else []
        safe_profile = _normalize_export_filename(profile_name or 'profile')
        base_name = _compute_export_filename(source_name, model_raw, bands)
        return base_name.replace('.csv', f'_{safe_profile}.csv')

    def _dedupe_export_rows(rows):
        grouped = {}
        for r in rows:
            key = (
                str(r.get('Frequency', '')).strip(),
                str(r.get('Duplex', '')).strip(),
                str(r.get('Offset', '')).strip(),
                str(r.get('Tone', '')).strip(),
                str(r.get('rToneFreq', '')).strip(),
                str(r.get('cToneFreq', '')).strip(),
                str(r.get('DtcsCode', '')).strip(),
                str(r.get('DtcsPolarity', '')).strip(),
                str(r.get('Mode', '')).strip(),
            )
            existing = grouped.get(key)
            if not existing or _row_score(r) > _row_score(existing):
                grouped[key] = r
        return list(grouped.values())

    def _format_export_statistics(df):
        band_counts = df['Band'].value_counts().to_dict() if 'Band' in df.columns else {}
        tone_counts = df['Tone'].value_counts().head(5).to_dict() if 'Tone' in df.columns else {}
        offset_counts = df['Offset'].value_counts().head(5).to_dict() if 'Offset' in df.columns else {}

        lines = [f"Channels exported: {len(df)}"]
        if band_counts:
            lines.append('Bands: ' + ', '.join(f'{k}={v}' for k, v in sorted(band_counts.items())))
        if tone_counts:
            lines.append('Top tones: ' + ', '.join(f'{k}={v}' for k, v in tone_counts.items()))
        if offset_counts:
            lines.append('Top offsets: ' + ', '.join(f'{k}={v}' for k, v in offset_counts.items()))
        return '\n'.join(lines)

    def compute_csv_row_hashes(csv_path):
        import csv as _csv, hashlib as _hashlib
        row_hashes = []
        with open(csv_path, newline='', encoding='utf-8') as rf:
            reader = _csv.reader(rf)
            headers = next(reader, None)
            for row in reader:
                row_hashes.append(_hashlib.sha256('\x1f'.join([str(cell) for cell in row]).encode('utf-8')).hexdigest())
        return headers, row_hashes

    def verify_export_file_hashes():
        paths = []
        for key in ('save_as_path', 'quick_export_path', 'preview_csv_path'):
            path = exported_data.get(key)
            if not path or not os.path.isfile(path):
                return
            paths.append((key, path))

        if len(paths) != 3:
            return

        try:
            file_hashes = [compute_csv_row_hashes(path) for _, path in paths]
            headers = [h for h, _ in file_hashes]
            if any(h != headers[0] for h in headers[1:]):
                raise ValueError('CSV column headers do not match.')
            rows_list = [rows for _, rows in file_hashes]
            if any(len(rows) != len(rows_list[0]) for rows in rows_list[1:]):
                raise ValueError('CSV row counts do not match.')
            for row_idx in range(len(rows_list[0])):
                row_hash = rows_list[0][row_idx]
                for other_rows in rows_list[1:]:
                    if other_rows[row_idx] != row_hash:
                        raise ValueError(f'Row {row_idx + 1} differs between export files.')
            messagebox.showinfo(
                'Export Verification',
                'Save As, Quick Export, and Preview CSV files have identical row hashes.'
            )
        except Exception as exc:
            messagebox.showerror(
                'Export Verification',
                f'Export file verification failed: {exc}'
            )

    def on_save_as():
        if exporting_flag.get('running'):
            messagebox.showwarning('Save As', 'Export in progress — please wait until it completes.')
            return
        df, pages = build_export_dataframe(show_warnings=True)
        if df is None or len(df) == 0:
            return
        exported_data['dataframe'] = df
        exported_data['row_count'] = len(df)
        exported_data['pages'] = pages or {}

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
                default_name = _get_default_export_filename_with_pages(exported_data.get('pages') or {})
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
            exported_data['save_as_path'] = save_path
            exported_data['last_export_path'] = save_path
            update_status_bar(exported_rows=total, profile_name=profile_var.get(), last_path=save_path)
            messagebox.showinfo('Done', f'Wrote {total} rows to {save_path}')
            verify_export_file_hashes()
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

    def load_recent_zip_set(zip_list):
        for idx, iv in enumerate(input_vars):
            iv.set(zip_list[idx] if idx < len(zip_list) else '')
        save_last_user_state(profile_var.get(), [iv.get().strip() for iv in input_vars])
        update_band_preview_and_summary()

    def batch_export():
        profile_names = sorted(band_profiles.keys())
        if not profile_names:
            messagebox.showwarning('Batch Export', 'No saved profiles to export.')
            return
        batch_win = tk.Toplevel(root)
        batch_win.title('Batch Export Profiles')
        batch_win.geometry('520x420')
        batch_win.transient(root)
        batch_win.grab_set()

        tk.Label(batch_win, text='Select saved profiles to export:', font=('Arial', 11, 'bold')).pack(anchor='w', padx=12, pady=(12, 4))
        listbox = tk.Listbox(batch_win, selectmode='multiple', height=10)
        listbox.pack(fill='both', expand=True, padx=12, pady=(0, 12))
        for name in profile_names:
            listbox.insert('end', name)

        def run_batch():
            selected = [profile_names[i] for i in listbox.curselection()]
            if not selected:
                messagebox.showwarning('Batch Export', 'Choose at least one profile.')
                return
            outdir = filedialog.askdirectory(initialdir=DEFAULT_SAVE_DIR, title='Select export folder')
            if not outdir:
                return
            errors = []
            count = 0
            for name in selected:
                apply_profile(name)
                df, pages = build_export_dataframe(show_warnings=False)
                if df is None or len(df) == 0:
                    errors.append(name)
                    continue
                safe_name = re.sub(r'[^A-Za-z0-9]+', '_', name).strip('_') or 'profile'
                from datetime import datetime
                save_path = os.path.join(outdir, f'FreqFinder_{safe_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
                try:
                    import csv as _csv
                    out_cols = list(df.columns)
                    write_export_csv(save_path, df)
                    count += 1
                except Exception:
                    errors.append(name)
            if errors:
                messagebox.showwarning('Batch Export', f'Export complete with errors. Failed: {", ".join(errors)}')
            else:
                messagebox.showinfo('Batch Export', f'Exported {count} profiles to {outdir}')
            batch_win.destroy()

        tk.Button(batch_win, text='Run Batch Export', command=run_batch, bg='#1976D2', fg='white', font=('Arial', 10), width=16).pack(pady=(0, 12))

    filemenu.add_command(label='Open File...', command=lambda: on_open_file())
    filemenu.add_command(label='Quick Export', command=lambda: on_quick_export())
    filemenu.add_command(label='Save As...', command=on_save_as)
    recent_zip_menu = tk.Menu(filemenu, tearoff=0)
    recent_sets = persistent_settings.get('recent_zip_sets', [])
    if recent_sets:
        for idx, zset in enumerate(recent_sets[:8]):
            label = f'{idx+1}: {", ".join(zset)}'
            recent_zip_menu.add_command(label=label, command=lambda z=zset: load_recent_zip_set(z))
    else:
        recent_zip_menu.add_command(label='No recent ZIP sets', state='disabled')
    filemenu.add_cascade(label='Recent ZIP Sets', menu=recent_zip_menu)
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
    
    # Callsign search menu
    callsignmenu = tk.Menu(menubar, tearoff=0)
    
    def show_callsign_search():
        search_window = tk.Toplevel(root)
        search_window.title('Callsign Search - QRZ Database')
        center_and_clamp(search_window, 500, 400)
        search_window.resizable(False, False)
        
        # Main frame
        main_frame = tk.Frame(search_window, padx=20, pady=20)
        main_frame.pack(fill='both', expand=True)
        
        # Title
        tk.Label(main_frame, text='QRZ Callsign Lookup', 
                font=('Arial', 12, 'bold')).pack(pady=(0, 15))
        
        # Callsign input
        input_frame = tk.Frame(main_frame)
        input_frame.pack(fill='x', pady=10)
        
        tk.Label(input_frame, text='Callsign:', font=('Arial', 10)).pack(side='left', padx=(0, 10))
        callsign_var = tk.StringVar()
        callsign_entry = tk.Entry(input_frame, textvariable=callsign_var, font=('Arial', 10), width=15)
        callsign_entry.pack(side='left')
        callsign_entry.focus()
        
        # Search button
        search_btn = tk.Button(input_frame, text='Search QRZ', command=lambda: perform_search(), 
                             font=('Arial', 10), width=12)
        search_btn.pack(side='left', padx=10)
            
        # Results area
        results_frame = tk.Frame(main_frame)
        results_frame.pack(fill='both', expand=True, pady=15)
        
        tk.Label(results_frame, text='QRZ Operator Information:', font=('Arial', 10, 'bold')).pack(anchor='w')
        
        # Results text widget with scrollbar
        results_container = tk.Frame(results_frame)
        results_container.pack(fill='both', expand=True)
        
        scrollbar = tk.Scrollbar(results_container)
        scrollbar.pack(side='right', fill='y')
        
        results_text = tk.Text(results_container, height=12, width=50, 
                            yscrollcommand=scrollbar.set, font=('Courier', 9))
        results_text.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=results_text.yview)
        
        # Simplified search function - QRZ only
        def perform_search():
            callsign = callsign_var.get().strip().upper()
            
            if not callsign:
                messagebox.showwarning('Input Required', 'Please enter a callsign.')
                return
                
            results_text.delete(1.0, tk.END)
            results_text.insert(tk.END, f'Searching QRZ for {callsign}...\n\n')
            search_window.update()
            
            try:
                qrz_results = scrape_qrz_gridmapper(callsign=callsign)
                
                if qrz_results:
                    results_text.insert(tk.END, f'✓ Found information for {callsign}\n\n')
                    for name, freq, tone, duplex, offset, notes in qrz_results:
                        results_text.insert(tk.END, f'{name}\n')
                        if freq:
                            results_text.insert(tk.END, f'  Frequency: {freq} MHz\n')
                        if tone:
                            results_text.insert(tk.END, f'  Tone: {tone}\n')
                        if notes:
                            results_text.insert(tk.END, f'  Notes: {notes}\n')
                        results_text.insert(tk.END, '\n')
                else:
                    results_text.insert(tk.END, f'No information found for {callsign}\n')
                    results_text.insert(tk.END, 'Note: QRZ requires login for detailed operator data.\n')
                    
            except Exception as e:
                results_text.insert(tk.END, f'Error searching QRZ: {str(e)}\n')
            
            results_text.see(tk.END)
        
        # Enter key binding
        callsign_entry.bind('<Return>', lambda e: perform_search())
        
    callsignmenu.add_command(label='Search Callsign...', command=show_callsign_search)
    menubar.add_cascade(label='Callsign', menu=callsignmenu)
    
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
    # How-To opens the project README
    def open_readme():
        try:
            from pathlib import Path
            readme = os.path.abspath(os.path.join(os.path.dirname(__file__), 'README.md'))
            webbrowser.open(Path(readme).as_uri())
        except Exception:
            try:
                pass
                # webbrowser.open('https://github.com/Drizztdowhateva/FreqFinder')  # preserved upstream reference for attribution
            except Exception:
                pass
    helpmenu.add_command(label='How-To', command=open_readme)
    # Link to RadioReference site
    def open_radioreference():
        try:
            webbrowser.open('https://www.radioreference.com')
        except Exception:
            pass
    helpmenu.add_command(label='RadioReference', command=open_radioreference)

    def show_races_help():
        races_window = tk.Toplevel(root)
        races_window.title('RACES & FCC Ham Radio Rules')
        races_window.resizable(True, True)
        center_and_clamp(races_window, 720, 600)

        canvas = tk.Canvas(races_window)
        scrollbar = ttk.Scrollbar(races_window, orient='vertical', command=canvas.yview)
        frame = tk.Frame(canvas)
        frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        title = tk.Label(frame, text='RACES & FCC Rules for Amateur Radio Operators', font=('Arial', 12, 'bold'), justify='left')
        title.pack(anchor='w', padx=15, pady=(12, 8))

        content = (
            'The Radio Amateur Civil Emergency Service (RACES) is a FCC-authorized amateur radio service that provides communications support during declared emergencies. '
            'RACES operation must follow FCC Part 97 rules, including station licensing, identification, and permitted frequency bands.\n\n'
            'Key points:\n'
            '• RACES stations may operate only when activated by civil authorities or an Emergency Management Agency.\n'
            '• Operators must hold a valid FCC Amateur Radio license.\n'
            '• Communications must use authorized frequencies and modes for the selected band.\n'
            '• RACES stations often use VHF/UHF repeaters, simplex channels, and national calling frequencies for emergency coordination.\n'
            '• When operating under RACES, the station should identify with the FCC-assigned call sign and the RACES station designation.\n\n'
            'Recommended practice:\n'
            '• Confirm local emergency communications plans and authorized RACES frequencies before deployment.\n'
            '• Use only the minimum power necessary for effective communication.\n'
            '• Avoid routine non-emergency traffic on RACES frequencies unless authorized.\n'
            '• If you are not a RACES participant, use standard amateur emergency procedures under ARES or general emergency traffic guidelines instead.\n\n'
            'This help text is intended as a general reference. Always consult the latest FCC Part 97 rules and your local emergency communications authority for official RACES operating requirements.'
        )
        label = tk.Label(frame, text=content, font=('Arial', 9), justify='left', wraplength=680, fg='#333333')
        label.pack(anchor='w', padx=15, pady=(0, 12))

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

    helpmenu.add_command(label='RACES Rules', command=show_races_help)

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
            webbrowser.open('https://github.com/Drizztdowhateva/FreqFinder')
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
            ('⏱ Scheduled Refresh',
             'Optionally re-fetch RadioReference pages on a configurable schedule so your'
             ' channel list stays up-to-date without manual intervention.'),
            ('🌐 Offline / Cached Mode',
             'Cache the last successful scrape result per URL so the app can be used offline,'
             ' falling back to cached data when RadioReference is unreachable.'),
            ('🔒 GMRS License Checker',
             'Optional reminder that GMRS operation requires an FCC license; add a gentle'
             ' warning when exporting GMRS channels without a stored license number.'),
            ('🛰 Enhanced Digital Tagging',
             'Expand protocol detection and export marking for P25, DMR, NXDN, and other'
             ' digital trunking systems so compatible radios can filter them reliably.'),
            ('📝 Notes & Labels',
             'Allow the user to attach free-text notes to individual channels before exporting,'
             ' stored in the CHIRP Comment field.'),
        ]

        for title_text, desc in improvements:
            tk.Label(sf, text=title_text, font=('Arial', 10, 'bold'),
                     justify='left').pack(anchor='w', padx=15, pady=(8, 2))
            tk.Label(sf, text=desc, font=('Arial', 9), justify='left',
                     wraplength=700, fg='#444444').pack(anchor='w', padx=30, pady=(0, 6))

        tk.Label(sf, text='👉 Have an idea? Open an issue on GitHub!',
                 font=('Arial', 9, 'italic'), fg='#0066cc').pack(anchor='w', padx=15, pady=(10, 6))

        def _open_issues():
            webbrowser.open('https://github.com/Drizztdowhateva/FreqFinder/issues')
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
        txt.insert('end', f'RadioReference index remote source: {get_remote_radioref_raw_url() or "not configured"}\n')
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

    def refresh_rr_index_ui():
        csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'radioref.csv'))
        refreshed = refresh_rr_index()
        if refreshed:
            messagebox.showinfo('RadioReference Index', f'radioref.csv was updated from online repository and saved to {csv_path}')
        else:
            if os.path.exists(csv_path):
                messagebox.showwarning('RadioReference Index', 'Could not refresh radioref.csv from the repository. Using local radioref.csv instead.')
            else:
                messagebox.showwarning('RadioReference Index', 'Could not refresh radioref.csv from the repository, and no local index is available.')

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
        'step_size': tk.IntVar(value=int(persistent_settings.get('last_step_size', 5)) if persistent_settings.get('last_step_size') is not None else 5),
        'preview_mode': tk.IntVar(value=int(persistent_settings.get('preview_mode', 1)) if persistent_settings.get('preview_mode') is not None else 1),
        'strict_freq_check': tk.IntVar(value=int(persistent_settings.get('strict_freq_check', 0)) if persistent_settings.get('strict_freq_check') is not None else 0),
        'auto_step_optimize': tk.IntVar(value=int(persistent_settings.get('auto_step_optimize', 0)) if persistent_settings.get('auto_step_optimize') is not None else 0),
        'filter_narrow_band': tk.IntVar(value=int(persistent_settings.get('filter_narrow_band', 0)) if persistent_settings.get('filter_narrow_band') is not None else 0),
        'sort_output': tk.IntVar(value=int(persistent_settings.get('sort_output', 0)) if persistent_settings.get('sort_output') is not None else 0),
        'remove_all_dups': tk.IntVar(value=int(persistent_settings.get('remove_all_dups', 0)) if persistent_settings.get('remove_all_dups') is not None else 0),
        'api_status': tk.StringVar(value='Loaded' if RR_API_KEY else 'Not loaded'),
        'model_features': {},
        'frs_gmrs_unlock': tk.IntVar(value=int(persistent_settings.get('frs_gmrs_unlock', 0)) if persistent_settings.get('frs_gmrs_unlock') is not None else 0),
        'scanner_mode': tk.IntVar(value=int(persistent_settings.get('scanner_mode', 0)) if persistent_settings.get('scanner_mode') is not None else 0),
        'scheduled_refresh': tk.IntVar(value=int(persistent_settings.get('scheduled_refresh', 0)) if persistent_settings.get('scheduled_refresh') is not None else 0),
        'offline_cache': tk.IntVar(value=int(persistent_settings.get('offline_cache', 0)) if persistent_settings.get('offline_cache') is not None else 0),
    }

    if persistent_settings.get('scheduled_refresh', 0) and not persistent_settings.get('offline_cache', 0):
        try:
            refresh_rr_index()
        except Exception:
            pass

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
        ToolTip(model_combo, 'Choose the radio model to match supported features and limit exports to compatible settings')

        tk.Label(radio_scrollable_frame, text='Data Source:', font=('Arial', 10, 'bold')).pack(anchor='w', padx=10, pady=(10, 5))
        source_var = tk.StringVar(value=preferences_data['selected_source'].get())
        source_combo = ttk.Combobox(radio_scrollable_frame, textvariable=source_var, state='readonly', width=40)
        source_combo['values'] = ['RadioReference', 'Radio Browser', 'RepeaterBook', 'QRZ Database', 'InterceptRadio']
        source_combo.pack(fill='x', padx=10, pady=(5, 10))
        source_desc_var = tk.StringVar(value='Choose data source: RadioReference (repeater/emergency), Radio Browser (FM broadcast), RepeaterBook (ham repeaters), QRZ Database (operator lookup), or InterceptRadio (ZIP-based ham frequencies).')
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
        
        # Add source selection handler for new sources
        def update_source_description(*args):
            selected_source = source_var.get()
            source_descriptions = {
                'RadioReference': 'RadioReference for repeater/emergency exports or Radio Browser for FM broadcast programming.',
                'Radio Browser': 'Radio Browser for FM broadcast programming.',
                'RepeaterBook': 'RepeaterBook for ham repeater databases.',
                'QRZ Database': 'QRZ Database for ham operator lookup.',
                'InterceptRadio': 'InterceptRadio for ZIP-based ham frequencies.'
            }
            source_desc_var.set(source_descriptions.get(selected_source, 'Select a data source.'))
        
        source_combo.bind('<<ComboboxSelected>>', update_source_description)
        update_source_description()  # Initial display
        
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

        step_label = tk.Label(export_scrollable_frame, text='Channel Step Size (kHz):', font=('Arial', 10, 'bold'))
        step_label.pack(anchor='w', padx=10, pady=(10, 4))
        step_size_var = tk.IntVar(value=preferences_data['step_size'].get())
        step_combo = ttk.Combobox(export_scrollable_frame, textvariable=step_size_var, state='readonly', width=10)
        step_combo['values'] = [5, 10, 12, 15, 20]
        step_combo.pack(anchor='w', padx=10, pady=(0, 10))
        ToolTip(step_combo, 'Select the radio channel step/increment size used in the exported programming file')

        preview_mode_var = tk.IntVar(value=preferences_data['preview_mode'].get())
        preview_mode_cb = tk.Checkbutton(export_scrollable_frame, text='Enable Preview Mode (show skip flags in CSV preview)', variable=preview_mode_var)
        preview_mode_cb.pack(anchor='w', padx=10, pady=(0, 12))
        ToolTip(preview_mode_cb, 'When enabled, Preview/Print shows the actual export CSV including Skip flags')
        
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
        tk.Button(api_scrollable_frame, text='Use built-in encrypted key', command=lambda: handle_api_choice('Use built-in (encrypted)'), bg='#1976D2', fg='white', width=20).pack(anchor='w', padx=10, pady=(0, 8))
        tk.Button(api_scrollable_frame, text='Refresh RadioReference index', command=refresh_rr_index_ui, bg='#1976D2', fg='white', width=28).pack(anchor='w', padx=10, pady=(0, 12))

        scheduled_refresh_var = tk.IntVar(value=preferences_data['scheduled_refresh'].get())
        scheduled_refresh_cb = tk.Checkbutton(api_scrollable_frame,
                                             text='Refresh RadioReference index on every load',
                                             variable=scheduled_refresh_var)
        scheduled_refresh_cb.pack(anchor='w', padx=10, pady=(4, 4))
        ToolTip(scheduled_refresh_cb, 'Attempt to refresh radioref.csv automatically at startup when internet access is available.')

        offline_cache_var = tk.IntVar(value=preferences_data['offline_cache'].get())
        offline_cache_cb = tk.Checkbutton(api_scrollable_frame,
                                          text='Use Offline / Cache mode (do not refresh automatically)',
                                          variable=offline_cache_var)
        offline_cache_cb.pack(anchor='w', padx=10, pady=(0, 12))
        ToolTip(offline_cache_cb, 'Use the local radioref.csv cache only. Automatic refresh is skipped when this option is enabled.')

        idx_status = 'present' if os.path.exists(os.path.join(os.path.dirname(__file__), 'radioref.csv')) else 'missing'
        tk.Label(api_scrollable_frame, text=f'Local RadioReference index is currently {idx_status}. If online, press Refresh to update; if offline, local data will be used.', wraplength=700, justify='left', fg='#666666', font=('Arial', 8)).pack(anchor='w', padx=10, pady=(0, 10))

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
            var = preferences_data.get(key) if preferences_data.get(key) else tk.IntVar(value=0)
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
            preferences_data['step_size'].set(step_size_var.get())
            preferences_data['preview_mode'].set(preview_mode_var.get())
            preferences_data['scanner_mode'].set(scanner_mode_var.get())
            preferences_data['frs_gmrs_unlock'].set(frs_pref_var.get())
            preferences_data['scheduled_refresh'].set(scheduled_refresh_var.get())
            preferences_data['offline_cache'].set(offline_cache_var.get())
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
                'last_step_size': preferences_data['step_size'].get(),
                'preview_mode': preferences_data['preview_mode'].get(),
                'strict_freq_check': preferences_data['strict_freq_check'].get(),
                'auto_step_optimize': preferences_data['auto_step_optimize'].get(),
                'filter_narrow_band': preferences_data['filter_narrow_band'].get(),
                'sort_output': preferences_data['sort_output'].get(),
                'remove_all_dups': preferences_data['remove_all_dups'].get(),
                'scheduled_refresh': preferences_data['scheduled_refresh'].get(),
                'offline_cache': preferences_data['offline_cache'].get(),
            })
            pref_window.destroy()
            messagebox.showinfo('Preferences', f'✓ Settings saved!\nRadio Model: {model_var.get()}\nQuality Level: {custom_var.get()}')
        
        def on_cancel():
            pref_window.destroy()
        
        tk.Button(button_frame, text='✓ Apply', command=on_apply, bg='#4CAF50', fg='white', width=12, font=('Arial', 10)).pack(side='right', padx=5)
        tk.Button(button_frame, text='Cancel', command=on_cancel, width=12, font=('Arial', 10)).pack(side='right', padx=5)

    
    # Remove Preferences from menubar - keep Advanced Settings in File menu

    filemenu.add_command(label='Advanced Settings...', command=open_preferences)

    # Attach Help menu after Preferences so order is File -> API -> Preferences -> Help
    menubar.add_cascade(label='Help', menu=helpmenu)
    root.config(menu=menubar)

    root.geometry('1100x700')
    root.resizable(True, True)
    root.grid_columnconfigure(2, weight=1)
    root.grid_columnconfigure(3, weight=1)

    donation_link = tk.Label(root, text=f'FreqFinder v{APP_VERSION} • Support', fg='#0066cc', cursor='hand2', font=('Arial', 10, 'underline'))
    donation_link.grid(row=0, column=0, columnspan=4, sticky='e', padx=8, pady=(6, 0))
    donation_link.bind('<Button-1>', lambda e: show_welcome_dialog())

    def show_welcome_dialog():
        dlg = tk.Toplevel(root)
        dlg.title('Welcome to FreqFinder')
        dlg.resizable(False, False)
        center_and_clamp(dlg, 580, 390)
        dlg.grab_set()
        dlg.transient(root)
        dlg.lift()
        dlg.focus()
        dlg.attributes('-topmost', True)

        banner = tk.Frame(dlg, bg='#1f2937')
        banner.pack(fill='x')
        tk.Label(banner, text='FreqFinder', bg='#1f2937', fg='white', font=('Arial', 16, 'bold')).pack(anchor='w', padx=18, pady=(14, 4))
        tk.Label(banner, text=f'Version {APP_VERSION}', bg='#1f2937', fg='#cbd5e1', font=('Arial', 10)).pack(anchor='w', padx=18, pady=(0, 14))

        body = tk.Frame(dlg, padx=18, pady=14)
        body.pack(fill='both', expand=True)

        left = tk.Frame(body)
        left.pack(side='left', fill='both', expand=True)
        right = tk.Frame(body, bd=1, relief='solid', padx=14, pady=14, bg='#f8fafc')
        right.pack(side='right', fill='y', padx=(12, 0))

        tk.Label(left, text='Welcome to FreqFinder', font=('Arial', 13, 'bold')).pack(anchor='w')
        tk.Label(left, text='Build high-quality radio channel exports quickly with support for repeaters, NOAA/MURS, FRS-GMRS, and Radio Browser FM data.',
                 wraplength=340, justify='left', fg='#334155', font=('Arial', 10)).pack(anchor='w', pady=(8, 12))

        intro_items = [
            'RadioReference for repeaters and emergency channels',
            'Radio Browser for FM broadcast station programming',
            'One ZIP mode can target ~80% radio capacity with top channels',
            'Use the tabbed pages to choose AM, NOAA/MURS, FRS-GMRS and Emergency',
        ]
        for item in intro_items:
            tk.Label(left, text=f'• {item}', wraplength=340, justify='left', fg='#334155', font=('Arial', 9)).pack(anchor='w', pady=2)

        tk.Label(right, text='Support the project', bg='#f8fafc', font=('Arial', 11, 'bold')).pack(anchor='w')
        tk.Label(right, text='Help keep the sources, scraping tools, and UI improvements maintained.',
                 wraplength=200, justify='left', bg='#f8fafc', fg='#475569', font=('Arial', 9)).pack(anchor='w', pady=(10, 14))
        tk.Button(right, text='Donate Now', bg='#2563eb', fg='white', font=('Arial', 10, 'bold'), width=20,
                  command=lambda: [dlg.destroy(), open_donations()]).pack(anchor='w')
        tk.Button(right, text='View GitHub', bg='#64748b', fg='white', font=('Arial', 10, 'bold'), width=20,
                  command=open_github).pack(anchor='w', pady=(10, 0))

        footer = tk.Frame(dlg)
        footer.pack(fill='x', padx=18, pady=(0, 14))
        tk.Button(footer, text='Get Started', command=dlg.destroy, bg='#10b981', fg='white', font=('Arial', 10, 'bold'), width=14).pack(side='right')

    if not persistent_settings.get('disable_startup_tips', 0):
        root.after(500, show_welcome_dialog)

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
    resolved_label_widgets = []
    last_zips = persistent_settings.get('last_zip_entries', [])
    input_start_row = 1

    band_tabs = ttk.Notebook(root)
    page_frames = {}
    for title, bands in PAGE_BAND_GROUPS:
        frame = ttk.Frame(band_tabs)
        band_tabs.add(frame, text=title)
        page_frames[title] = frame

    zip_frame = tk.Frame(page_frames['Zip Code'])
    zip_frame.pack(fill='both', expand=True, padx=8, pady=8)

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
            resolved_label_widgets[idx].config(fg='#666666')
            return
        tokens = parse_input_tokens(v)
        band_tokens = extract_band_tokens(v)
        url_tokens = [tok for tok in tokens if tok.startswith('http://') or tok.startswith('https://')]
        zip_tokens = [tok for tok in tokens if re.fullmatch(r'^\d{5}$', tok)]

        if url_tokens:
            label = get_location_from_url(url_tokens[0]) or ''
            msg = f'URL detected ✓ {label}'
            if band_tokens:
                msg += f' | Bands: {", ".join(band_tokens)}'
            resolved_labels[idx].set(msg)
            resolved_label_widgets[idx].config(fg='#008000')
            return

        if zip_tokens:
            v = zip_tokens[0]
            try:
                pr = http_get(f'http://api.zippopotam.us/us/{v}', timeout=6)
                if pr.status_code == 200:
                    pj = pr.json()
                    places = pj.get('places', [])
                else:
                    # ZIP not found, use basic ZIP search
                    places = []
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
                            msg = f'✓ {county}, {state}  '
                            msg += f'(ctid {ctid})' if ctid else '(no ctid)'
                            if band_tokens:
                                msg += f' | Bands: {", ".join(band_tokens)}'
                            resolved_labels[idx].set(msg)
                            resolved_label_widgets[idx].config(fg='#008000')
                            return
            except Exception:
                pass

        if band_tokens:
            resolved_labels[idx].set(f'Band tokens: {", ".join(band_tokens)}')
            resolved_label_widgets[idx].config(fg='#0066CC')
            return

        # otherwise, show raw value
        resolved_labels[idx].set('✗ Invalid ZIP/URL')
        resolved_label_widgets[idx].config(fg='#AA0000')

    for i, iv in enumerate(input_vars, start=1):
        if i <= len(last_zips):
            iv.set(last_zips[i-1])

        label = tk.Label(zip_frame, text=f'Zip Code {i}:')
        label.grid(row=input_start_row + i-1, column=0, sticky='e', padx=(4, 50), pady=2)
        ToolTip(label, 'Enter a 5-digit ZIP code or RadioReference URL\nto search for frequencies in that area')
        
        ent = tk.Entry(zip_frame, textvariable=iv, width=14)
        ent.grid(row=input_start_row + i-1, column=1, sticky='w', padx=0, pady=2)
        ToolTip(ent, 'ZIP Code: Searches for repeaters in that area\nURL: Directly uses RadioReference page\nBand tokens like 2m, 70cm, 1.25m, NOAA, Emergency are recognized and applied as selected bands.')
        
        resolved_lbl = tk.Label(zip_frame, textvariable=resolved_labels[i-1], anchor='w', fg='#666666', wraplength=320, justify='left')
        resolved_lbl.grid(row=input_start_row + i-1, column=2, columnspan=2, sticky='w', padx=4, pady=2)
        resolved_label_widgets.append(resolved_lbl)
        ToolTip(resolved_lbl, 'Shows the county/state location found\nand its RadioReference ID (ctid)')
        
        iv.trace_add('write', lambda *_i, idx=i-1: resolve_input(idx))
        if iv.get().strip():
            resolve_input(i-1)

    # Bands profile system and tabbed band plan selection
    start_row = input_start_row + len(input_vars)
    local_settings = load_persistent_settings()
    band_profiles = local_settings.get('band_profiles', {}) or {}
    for name, profile in DEFAULT_BAND_PROFILES.items():
        band_profiles.setdefault(name, profile)

    def save_band_profiles():
        nonlocal band_profiles
        settings = load_persistent_settings()
        settings['band_profiles'] = band_profiles
        save_persistent_settings(settings)

    def refresh_profile_list():
        names = sorted(band_profiles.keys())
        profile_combo['values'] = names
        try:
            profile_compare_combo['values'] = names
        except Exception:
            pass

    def get_selected_band_order():
        return [band_listbox.get(i) for i in range(band_listbox.size())]

    def set_selected_bands(bands, order=None):
        band_listbox.delete(0, tk.END)
        if order is None:
            order = bands
        for band in order:
            if band in BAND_RANGES and band in bands:
                band_listbox.insert(tk.END, band)
        for band in bands:
            if band in BAND_RANGES and band not in order:
                band_listbox.insert(tk.END, band)
        for band, var in band_vars.items():
            var.set(1 if band in bands else 0)

    def apply_profile(name):
        if not name or name not in band_profiles:
            return
        profile = band_profiles[name]
        bands = profile.get('bands', [])
        order = profile.get('order', bands)
        set_selected_bands(bands, order)
        for et, var in emergency_filter_vars.items():
            var.set(1 if et in profile.get('emergency_types', list(EMERGENCY_TYPE_KEYWORDS.keys())) else 0)
        if 'scanner_mode' in profile:
            preferences_data['scanner_mode'].set(1 if profile.get('scanner_mode') else 0)
        if 'selected_source' in profile:
            preferences_data['selected_source'].set(profile.get('selected_source', preferences_data['selected_source'].get()))
        if 'selected_model' in profile:
            preferences_data['selected_model'].set(profile.get('selected_model', preferences_data['selected_model'].get()))
        if 'customization_level' in profile:
            preferences_data['customization_level'].set(profile.get('customization_level', preferences_data['customization_level'].get()))
        if 'frs_gmrs_unlock' in profile:
            preferences_data['frs_gmrs_unlock'].set(1 if profile.get('frs_gmrs_unlock') else 0)
        if 'zip_entries' in profile:
            entries = profile.get('zip_entries', [])
            for idx, iv in enumerate(input_vars):
                iv.set(entries[idx] if idx < len(entries) else '')
        profile_var.set(name)
        try:
            enforce_model_constraints()
        except Exception:
            pass
        update_band_preview_and_summary()
        save_last_user_state(name, [iv.get().strip() for iv in input_vars])

    def save_profile():
        name = profile_name_var.get().strip()
        if not name:
            messagebox.showwarning('Band Profiles', 'Enter a profile name to save.')
            return
        profile = {
            'bands': [band for band in get_selected_band_order()],
            'order': get_selected_band_order(),
            'emergency_types': [et for et, var in emergency_filter_vars.items() if var.get()],
            'scanner_mode': bool(preferences_data.get('scanner_mode').get() if preferences_data.get('scanner_mode') else 0),
            'selected_source': preferences_data.get('selected_source').get() if preferences_data.get('selected_source') else 'RadioReference',
            'selected_model': preferences_data.get('selected_model').get() if preferences_data.get('selected_model') else 'Generic',
            'customization_level': preferences_data.get('customization_level').get() if preferences_data.get('customization_level') else 'Default',
            'frs_gmrs_unlock': bool(preferences_data.get('frs_gmrs_unlock').get() if preferences_data.get('frs_gmrs_unlock') else 0),
            'zip_entries': [iv.get().strip() for iv in input_vars],
        }
        band_profiles[name] = profile
        save_band_profiles()
        refresh_profile_list()
        profile_var.set(name)
        save_last_user_state(name, [iv.get().strip() for iv in input_vars])
        messagebox.showinfo('Band Profiles', f'Profile "{name}" saved.')

    def load_profile():
        name = profile_var.get()
        if not name:
            messagebox.showwarning('Band Profiles', 'Choose a saved profile to load.')
            return
        apply_profile(name)
        messagebox.showinfo('Band Profiles', f'Profile "{name}" loaded.')

    def delete_profile():
        name = profile_var.get()
        if not name or name not in band_profiles:
            messagebox.showwarning('Band Profiles', 'Choose a saved profile to delete.')
            return
        if messagebox.askyesno('Band Profiles', f'Delete profile "{name}"?'):
            band_profiles.pop(name, None)
            save_band_profiles()
            refresh_profile_list()
            profile_var.set('')
            messagebox.showinfo('Band Profiles', f'Profile "{name}" deleted.')

    def save_profile_as():
        name = simpledialog.askstring('Save Profile As', 'Enter a new profile name:', parent=root)
        if not name:
            return
        profile_name_var.set(name)
        save_profile()

    def compare_profiles():
        left_name = profile_var.get()
        right_name = profile_compare_var.get()
        if not left_name or not right_name:
            messagebox.showwarning('Profile Compare', 'Select two profiles to compare.')
            return
        if left_name == right_name:
            messagebox.showinfo('Profile Compare', 'Choose two different profiles to compare.')
            return
        left = band_profiles.get(left_name, {})
        right = band_profiles.get(right_name, {})
        diff = []
        for key in ['bands', 'order', 'emergency_types', 'scanner_mode', 'selected_source', 'selected_model', 'customization_level', 'frs_gmrs_unlock']:
            left_val = left.get(key)
            right_val = right.get(key)
            if left_val != right_val:
                diff.append(f'{key}: {left_name}={left_val} | {right_name}={right_val}')
        if not diff:
            messagebox.showinfo('Profile Compare', f'Profiles "{left_name}" and "{right_name}" are identical in saved settings.')
            return
        compare_text = '\n'.join(diff)
        compare_win = tk.Toplevel(root)
        compare_win.title('Profile Comparison')
        compare_win.geometry('600x360')
        compare_win.transient(root)
        compare_win.grab_set()
        text = tk.Text(compare_win, wrap='word', font=('Arial', 10))
        text.pack(fill='both', expand=True, padx=10, pady=10)
        text.insert('end', compare_text)
        text.config(state='disabled')
        tk.Button(compare_win, text='Close', command=compare_win.destroy, width=10).pack(pady=(0,10))

    profile_frame = tk.Frame(root)
    profile_frame.grid(row=start_row, column=0, columnspan=3, sticky='we', padx=4, pady=(4, 2))
    profile_frame.grid_columnconfigure(1, weight=1)
    profile_frame.grid_columnconfigure(2, weight=0)

    tk.Label(profile_frame, text='Band Profile:').grid(row=0, column=0, sticky='w')
    profile_var = tk.StringVar(value=persistent_settings.get('last_band_profile', ''))
    profile_combo = ttk.Combobox(profile_frame, textvariable=profile_var, state='readonly', width=28)
    profile_combo.grid(row=0, column=1, sticky='we', padx=(4, 0))

    profile_actions_frame = tk.Frame(profile_frame)
    profile_actions_frame.grid(row=0, column=2, rowspan=4, sticky='nw', padx=(12, 0))

    tk.Button(profile_actions_frame, text='Load', command=load_profile, width=8).grid(row=0, column=0, padx=3, pady=2)
    tk.Button(profile_actions_frame, text='Delete', command=delete_profile, width=8).grid(row=0, column=1, padx=3, pady=2)
    tk.Button(profile_actions_frame, text='Compare', command=compare_profiles, width=10).grid(row=0, column=2, padx=3, pady=2)

    tk.Label(profile_frame, text='Profile name:').grid(row=1, column=0, sticky='w', pady=(6, 0))
    profile_name_var = tk.StringVar()
    tk.Entry(profile_frame, textvariable=profile_name_var, width=30).grid(row=1, column=1, sticky='we', padx=(4, 0), pady=(6, 0))
    tk.Button(profile_actions_frame, text='Save', command=save_profile, width=8).grid(row=1, column=0, padx=3, pady=2)
    tk.Button(profile_actions_frame, text='Save As...', command=save_profile_as, width=10).grid(row=1, column=1, padx=3, pady=2)

    tk.Label(profile_frame, text='Compare to:').grid(row=2, column=0, sticky='w', pady=(6, 0))
    profile_compare_var = tk.StringVar(value='')
    profile_compare_combo = ttk.Combobox(profile_frame, textvariable=profile_compare_var, state='readonly', width=26)
    profile_compare_combo.grid(row=2, column=1, sticky='we', padx=(4, 0), pady=(6, 0))
    tk.Button(profile_actions_frame, text='Emergency', command=lambda: apply_profile('Emergency Comms'), width=11).grid(row=2, column=0, padx=3, pady=2)
    tk.Button(profile_actions_frame, text='Traveler', command=lambda: apply_profile('Traveler'), width=10).grid(row=2, column=1, padx=3, pady=2)
    tk.Button(profile_actions_frame, text='HamScan', command=lambda: apply_profile('HamScan'), width=10).grid(row=2, column=2, padx=3, pady=2)

    band_tabs.grid(row=start_row+1, column=0, columnspan=2, sticky='nsew', padx=8, pady=4)
    root.grid_rowconfigure(start_row+1, weight=1)
    root.grid_columnconfigure(0, weight=1)
    root.grid_columnconfigure(1, weight=1)

    band_vars = {}
    emergency_filter_vars = {}
    band_listbox = tk.Listbox(page_frames['Ham-SSB/AM'], height=8)
    band_listbox.grid(row=0, column=0, rowspan=10, sticky='n', padx=8, pady=4)
    ToolTip(band_listbox, 'Drag and drop or use Up/Down buttons to reorder bands\nTop band appears first in export')
    ToolTip(band_listbox, 'Drag and drop or use Up/Down buttons to reorder bands\nTop band appears first in export')
    
    tk.Label(page_frames['Ham-SSB/AM'], text='High-quality frequency band selection: best used with one ZIP code for local coverage.', font=('Arial', 9), fg='#555').grid(row=10, column=0, columnspan=3, sticky='w', padx=10, pady=(4, 0))

    drag_data = {'item': None, 'index': None}
    def on_band_drag_start(event):
        idx = band_listbox.nearest(event.y)
        if idx >= 0 and idx < band_listbox.size():
            drag_data['index'] = idx
            drag_data['item'] = band_listbox.get(idx)
    def on_band_drag_motion(event):
        if drag_data['item'] is None:
            return
        idx = band_listbox.nearest(event.y)
        if idx >= 0 and idx < band_listbox.size() and idx != drag_data['index']:
            band_listbox.delete(drag_data['index'])
            band_listbox.insert(idx, drag_data['item'])
            band_listbox.selection_clear(0, 'end')
            band_listbox.selection_set(idx)
            drag_data['index'] = idx
    def on_band_drag_release(event):
        if drag_data['item'] is not None:
            update_band_preview_and_summary()
            drag_data['item'] = None
            drag_data['index'] = None
    band_listbox.bind('<ButtonPress-1>', on_band_drag_start)
    band_listbox.bind('<B1-Motion>', on_band_drag_motion)
    band_listbox.bind('<ButtonRelease-1>', on_band_drag_release)

    band_search_var = tk.StringVar()
    scope_search_var = tk.StringVar()
    scope_only_var = tk.IntVar(value=0)
    def filter_band_checkbuttons(*args):
        query = band_search_var.get().strip().lower()
        for band, cb in band_checkbuttons.items():
            if not query or query in band.lower():
                try:
                    cb.grid()
                except Exception:
                    pass
            else:
                try:
                    cb.grid_remove()
                except Exception:
                    pass
    band_search_var.trace_add('write', filter_band_checkbuttons)

    def get_scope_keywords():
        return [tok.strip().lower() for tok in re.split(r'[\n,]+', scope_search_var.get() or '') if tok.strip()]

    def move_up():
        sel = band_listbox.curselection()
        if not sel:
            return
        i = sel[0]
        if i == 0:
            return
        txt = band_listbox.get(i)
        band_listbox.delete(i)
        band_listbox.insert(i-1, txt)
        band_listbox.selection_set(i-1)
        update_band_preview_and_summary()

    def move_down():
        sel = band_listbox.curselection()
        if not sel:
            return
        i = sel[0]
        if i == band_listbox.size()-1:
            return
        txt = band_listbox.get(i)
        band_listbox.delete(i)
        band_listbox.insert(i+1, txt)
        band_listbox.selection_set(i+1)
        update_band_preview_and_summary()

    # Add Up/Down buttons to Ham-SSB/AM page (now that functions are defined)
    band_control_frame = tk.Frame(page_frames['Ham-SSB/AM'])
    band_control_frame.grid(row=0, column=1, sticky='n', padx=4, pady=4)
    up_btn = tk.Button(band_control_frame, text='Up', command=move_up, width=6, height=2)
    up_btn.grid(row=0, column=0, padx=2, pady=2)
    ToolTip(up_btn, 'Move selected band up in priority')
    down_btn = tk.Button(band_control_frame, text='Down', command=move_down, width=6, height=2)
    down_btn.grid(row=1, column=0, padx=2, pady=2)
    ToolTip(down_btn, 'Move selected band down in priority')

    search_frame = tk.Frame(zip_frame)
    search_frame.grid(row=input_start_row + len(input_vars), column=0, sticky='w', padx=4, pady=(12, 2))
    tk.Label(search_frame, text='Filter bands:').grid(row=0, column=0, sticky='w')
    search_entry = tk.Entry(search_frame, textvariable=band_search_var, width=18)
    search_entry.grid(row=0, column=1, sticky='w', padx=(4,0))
    ToolTip(search_entry, 'Filter the available band checkboxes by name')

    tk.Label(search_frame, text='Locality:').grid(row=1, column=0, sticky='w', pady=(4,0))
    scope_entry = tk.Entry(search_frame, textvariable=scope_search_var, width=18)
    scope_entry.grid(row=1, column=1, sticky='w', padx=(4,0), pady=(4,0))
    ToolTip(scope_entry, 'Enter preferred locality keywords to rank nearby channels higher. Examples: Evanston, Skokie, Rogers Park')

    scope_only_cb = tk.Checkbutton(search_frame, text='Local Calling Frequencies', variable=scope_only_var,
                                   command=lambda: update_band_preview_and_summary())
    scope_only_cb.grid(row=2, column=0, columnspan=2, sticky='w', pady=(4,0))
    ToolTip(scope_only_cb, 'When enabled, only rows matching the locality keywords will be returned')

    
    frs_unlock_var = preferences_data.get('frs_gmrs_unlock') if preferences_data.get('frs_gmrs_unlock') else tk.IntVar(value=0)
    frs_unlock_cb = tk.Checkbutton(search_frame, text='Ensure FRS/GMRS unlocked & enable bandplan', variable=frs_unlock_var)
    frs_unlock_cb.grid(row=1, column=0, columnspan=3, sticky='w', pady=(8, 0))
    ToolTip(frs_unlock_cb, 'Mark FRS/GMRS fixed channels as unlocked for programming (requires firmware unlock on your radio)')

    band_preview_frame = tk.LabelFrame(root, text='Band Plan Preview', padx=4, pady=4)
    band_preview_frame.grid(row=start_row+1, column=2, columnspan=2, rowspan=1, sticky='nsew', padx=4, pady=2)
    band_preview_text = tk.Text(band_preview_frame, wrap='word', font=('Arial', 9), bg=band_preview_frame.cget('bg'), bd=0, highlightthickness=0, height=8)
    band_preview_text.pack(fill='both', expand=True)
    band_preview_text.insert('1.0', '')
    band_preview_text.config(state='disabled')

    export_summary_frame = tk.LabelFrame(root, text='Export Summary', padx=4, pady=4)
    export_summary_frame.grid(row=start_row+2, column=2, columnspan=2, rowspan=2, sticky='nsew', padx=4, pady=2)
    root.grid_rowconfigure(start_row+2, weight=1)
    export_summary_text = tk.Text(export_summary_frame, height=10, width=40, wrap='word', font=('Arial', 9))
    export_summary_text.pack(fill='both', expand=True)
    export_summary_scrollbar = tk.Scrollbar(export_summary_frame, command=export_summary_text.yview)
    export_summary_text.config(yscrollcommand=export_summary_scrollbar.set)

    def update_band_preview_and_summary():
        bands = get_selected_band_order()
        if bands:
            lines = [f'Selected bands ({len(bands)}):', ', '.join(bands), '']
        else:
            lines = ['Selected bands: None', '']
        if 'NOAA' in bands:
            lines.append(f'NOAA weather channels: {len(NOAA_FREQS)}')
        if 'MURS' in bands:
            lines.append(f'MURS channels: {len(MURS_FREQS)}')
        if 'FRS/GMRS' in bands:
            lines.append(f'FRS/GMRS channels: {len(FRS_GMRS_FREQS)}')
        if 'Emergency' in bands:
            lines.append('Emergency: variable repeater dispatch channels')
            emergency_types = [et for et, var in emergency_filter_vars.items() if var.get()]
            if emergency_types:
                lines.append(f'Emergency types: {", ".join(emergency_types)}')
                term_lines = []
                for et in emergency_types:
                    term_lines.append(f'{et} [{", ".join(EMERGENCY_TYPE_KEYWORDS.get(et, []))}]')
                lines.append('Matching terms: ' + '; '.join(term_lines))
            else:
                lines.append('Emergency filter active: no emergency types selected')
        if any(b in ('2m','70cm','1.25m') for b in bands):
            lines.append('Repeater bands: area-specific channels from RadioReference')
            lines.append('Note: Same callsign with different frequencies = separate repeaters or modes')
        lines.append('')
        lines.append(f'Profile: {profile_var.get() or "None"}')
        lines.append(f'Scanner mode: {"On" if preferences_data.get("scanner_mode").get() else "Off"}')

        source_name = preferences_data.get('selected_source').get() if preferences_data.get('selected_source') else 'RadioReference'
        if source_name == 'Radio Browser':
            lines.append('NOTE: Band plan preview is unavailable with Radio Browser. Use RadioReference for repeater/Emergency band plans.')
        summary_lines = [
            f'Preview Mode: {"CSV with skip flags" if preferences_data.get("preview_mode").get() else "Summary only"}',
            f'Data source: {source_name}',
            ''
        ]
        zip_count = sum(1 for iv in input_vars if re.fullmatch(r'^\d{5}$', iv.get().strip()))
        if source_name == 'RadioReference' and zip_count == 1 and preferences_data.get('customization_level').get() in ('Advanced', 'High Quality'):
            summary_lines.append('Quality target: selecting the best channels up to 80% of radio capacity.')
            summary_lines.append('')
        selected = get_selected_band_order()
        summary_lines.append(f'Ordered selection: {" > ".join(selected) if selected else "None"}')
        emergency_types = [et for et, var in emergency_filter_vars.items() if var.get()]
        if emergency_types:
            summary_lines.append(f'Selected emergency types: {", ".join(emergency_types)}')
        scope_keywords = get_scope_keywords()
        if scope_only_var.get():
            summary_lines.append('Local only: On')
        if scope_keywords:
            summary_lines.append(f'Locality keywords: {", ".join(scope_keywords)}')
        elif scope_only_var.get():
            summary_lines.append('Local only enabled; no locality keywords set')
        band_preview_text.config(state='normal')
        band_preview_text.delete('1.0', 'end')
        band_preview_text.insert('1.0', '\n'.join(lines))
        band_preview_text.config(state='disabled')
        export_summary_text.config(state='normal')
        export_summary_text.delete('1.0', 'end')
        export_summary_text.insert('1.0', '\n'.join(summary_lines))
        export_summary_text.config(state='disabled')

    def refresh_ui_state(*args):
        update_band_preview_and_summary()
    band_search_var.trace_add('write', lambda *_: refresh_ui_state())
    scope_search_var.trace_add('write', lambda *_: refresh_ui_state())
    scope_only_var.trace_add('write', lambda *_: refresh_ui_state())
    def toggle_band(band):
        if band_vars[band].get():
            if band not in band_listbox.get(0, tk.END):
                band_listbox.insert(tk.END, band)
        else:
            for i in range(band_listbox.size()-1, -1, -1):
                if band_listbox.get(i) == band:
                    band_listbox.delete(i)
        update_band_preview_and_summary()

    for page_title, bands in PAGE_BAND_GROUPS:
        frame = page_frames[page_title]
        for j, band in enumerate(bands):
            v = tk.IntVar(value=1 if band in ('70cm', '2m') else 0)
            band_vars[band] = v
            cb = tk.Checkbutton(frame, text=band, variable=v, command=lambda b=band: toggle_band(b))
            
            # For Ham-SSB/AM page, organize HAM bands together with proper spacing
            if page_title == 'Ham-SSB/AM':
                if band in HAM_BANDS:
                    # Group HAM bands in right column next to border, no overlap
                    cb.grid(row=j, column=2, sticky='e', padx=(10, 20), pady=(4 if j == 0 else 2))
                else:
                    # Non-HAM bands in left column
                    cb.grid(row=j, column=0, sticky='w', padx=10, pady=(4 if j == 0 else 2))
            else:
                cb.grid(row=j, column=0, sticky='w', padx=10, pady=4)
            band_checkbuttons[band] = cb
            if band == '10m':
                ToolTip(cb, '10m band (28.0-29.7 MHz)\nHigh Frequency - long-distance communication')
            elif band == '6m':
                ToolTip(cb, '6m band (50.0-54.0 MHz)\nMedium Frequency - extended range coverage')
            elif band == '2m':
                ToolTip(cb, '2m band (144-148 MHz)\nVery High Frequency - wider area coverage')
            elif band == '1.25m':
                ToolTip(cb, '1.25m band (222-225 MHz)\n220 MHz band - local repeater coverage')
            elif band == '70cm':
                ToolTip(cb, '70cm band (420-450 MHz)\nUltra High Frequency - local area coverage')
            elif band == '33cm':
                ToolTip(cb, '33cm band (902-928 MHz)\n900 MHz band - short-range communication')
            elif band == '23cm':
                ToolTip(cb, '23cm band (1240-1300 MHz)\n1.2 GHz band - very short-range communication')
            elif band == 'NOAA':
                ToolTip(cb, 'NOAA Weather Alerts (162.4-162.55 MHz)\nPublic weather radio broadcasts')
            elif band == 'MURS':
                ToolTip(cb, 'MURS (151.82-154.6 MHz)\nMulti-Use Radio Service - license-free')
            elif band == 'FRS/GMRS':
                ToolTip(cb, 'FRS/GMRS (462-467 MHz)\nFamily Radio Service / General Mobile Radio Service')
            elif band == 'Emergency':
                ToolTip(cb, 'Emergency / Public Safety dispatch frequencies\nSearches county/zip pages for Police/Fire/EMS/citywide analog channels')
            if v.get():
                band_listbox.insert(tk.END, band)

    # Emergency subtype filters appear on the Emergency tab
    emergency_frame = page_frames['Emergency']
    tk.Label(emergency_frame, text='Emergency selection is optimized for high-quality public safety channels. High Quality export mode will try to use the best channels within 80% of your radio capacity.', wraplength=380, justify='left', font=('Arial', 9), fg='#555').grid(row=0, column=0, columnspan=2, sticky='w', padx=10, pady=(6, 0))
    tk.Label(emergency_frame, text='Emergency Types:', font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', padx=10, pady=(10, 4))
    for i, et in enumerate(EMERGENCY_TYPE_KEYWORDS.keys()):
        ve = tk.IntVar(value=1)
        emergency_filter_vars[et] = ve
        cb = tk.Checkbutton(emergency_frame, text=et, variable=ve, command=lambda: refresh_ui_state())
        cb.grid(row=2 + i//2, column=i%2, sticky='w', padx=12, pady=4)

    refresh_profile_list()
    last_profile_name = persistent_settings.get('last_band_profile', '')
    if last_profile_name and last_profile_name in band_profiles:
        apply_profile(last_profile_name)
        profile_var.set(last_profile_name)
    update_band_preview_and_summary()

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
        try:
            _suppress_messageboxes(True)
        except Exception:
            pass
        try:
            export_btn.config(state='disabled')
        except Exception:
            pass

        try:
            df, pages = build_export_dataframe(show_warnings=True)
            if df is None or len(df) == 0:
                cleanup_export()
                return

            try:
                from datetime import datetime
                model_raw = preferences_data.get('selected_model').get() if preferences_data.get('selected_model') else 'Generic'
                model_s = re.sub(r'[^A-Za-z0-9]+', '_', model_raw).strip('_') or 'Model'

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
                default_name = _get_default_export_filename_with_pages(pages)
            except Exception:
                default_name = 'chirp_output.csv'

            initial_dir = DEFAULT_SAVE_DIR if os.path.isdir(DEFAULT_SAVE_DIR) else None
            save_path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV files','*.csv'),('All files','*.*')], initialdir=initial_dir, initialfile=default_name, title='Save CSV as')
            if not save_path:
                cleanup_export()
                return

            write_export_csv(save_path, df)
            exported_data['last_export_path'] = save_path
            update_status_bar(exported_rows=len(df), profile_name=profile_var.get(), last_path=save_path)
            stats_text = exported_data.get('export_stats', '')
            done_text = f'Wrote {len(df)} rows to {save_path}'
            if stats_text:
                done_text = f'{done_text}\n\nExport summary:\n{stats_text}'
            messagebox.showinfo('Done', done_text)
        except Exception as e:
            messagebox.showerror('Export', f'Failed to export CSV: {e}')
        finally:
            cleanup_export()

    def build_export_dataframe(show_warnings=True):
        selected_source = preferences_data.get('selected_source').get() if preferences_data.get('selected_source') else 'RadioReference'
        scanner_mode_enabled = bool(preferences_data.get('scanner_mode').get() if preferences_data.get('scanner_mode') else 0)
        zip_present = any(re.match(r'^\d{5}$', iv.get().strip() or '') for iv in input_vars)
        band_selected = any(v.get() for v in band_vars.values())

        if selected_source == 'Radio Browser' and not zip_present:
            if show_warnings:
                messagebox.showerror('Error', 'Radio Browser source requires at least one valid ZIP code')
            return None, None
        if selected_source != 'Radio Browser' and (not zip_present or not band_selected):
            if show_warnings:
                messagebox.showerror('Error', 'Must have at least one ZIP code and at least one band selected')
            return None, None

        pages = {}
        input_band_tokens = []
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
                if show_warnings:
                    messagebox.showerror('Error', 'No Radio Browser station results were found for the selected ZIPs.')
                return None, None
            try:
                import pandas as pd
                outdf = pd.DataFrame(rows_rb)
                exported_data['dataframe'] = outdf
                exported_data['row_count'] = len(outdf)
                exported_data['pages'] = {}
                return outdf, {}
            except Exception as exc:
                if show_warnings:
                    messagebox.showerror('Error', f'Failed building Radio Browser preview: {exc}')
                return None, None

        input_band_tokens = []
        page_entries = []
        for idx, iv in enumerate(input_vars):
            raw_value = iv.get().strip()
            if not raw_value:
                continue
            tokens = parse_input_tokens(raw_value)
            band_tokens = expand_band_tokens(tokens)
            for band in band_tokens:
                if band and band not in input_band_tokens:
                    input_band_tokens.append(band)
            page_entries.extend(build_radioreference_page_entries(tokens, rr_index))
        if input_band_tokens:
            current_bands = get_selected_band_order()
            for band in input_band_tokens:
                if band not in current_bands:
                    current_bands.append(band)
            set_selected_bands(current_bands, order=current_bands)
        if page_entries:
            pages = {label: url for label, url, _ in page_entries}
        if not pages:
            pages = {k: v for k, v in default_pages.items()}

        save_last_user_state(profile_var.get(), [iv.get().strip() for iv in input_vars])

        sel_bands = [band_listbox.get(i) for i in range(band_listbox.size())]
        if not sel_bands:
            if show_warnings:
                messagebox.showerror('Error', 'Select at least one band to export')
            return None, None

        sel_name = preferences_data.get('selected_model').get() if preferences_data.get('selected_model') else 'Generic'
        model_key = next((k for k, v in RADIO_MODELS.items() if v['name'] == sel_name), 'Generic')
        model_obj = RADIO_MODELS.get(model_key, RADIO_MODELS['Generic'])
        max_channels = model_obj.get('max_channels')
        cust_level = preferences_data.get('customization_level').get() if preferences_data.get('customization_level') else 'Default'

        rows = []
        fetch_errors = []
        if not page_entries:
            page_entries = [(label, url, None) for label, url in pages.items()]
        page_results = []
        for label, u, zip_code in page_entries:
            try:
                page_rows = list(fetch_freqs_for_page(u))
                
                # Try additional sources if RadioReference returns no results
                if not page_rows and zip_code:
                    all_source_results = []
                    
                    # Try RepeaterBook
                    try:
                        rb_rows = scrape_repeaterbook(zipcode=zip_code)
                        if rb_rows:
                            all_source_results.extend(rb_rows)
                            logger.info(f"RepeaterBook found {len(rb_rows)} results for {zip_code}")
                    except Exception as e:
                        logger.error(f"RepeaterBook failed: {e}")
                    
                    # Try InterceptRadio
                    try:
                        ir_rows = scrape_intercept_radio(zip_code)
                        if ir_rows:
                            all_source_results.extend(ir_rows)
                            logger.info(f"InterceptRadio found {len(ir_rows)} results for {zip_code}")
                    except Exception as e:
                        logger.error(f"InterceptRadio failed: {e}")
                    
                    # Validate and deduplicate all results
                    if all_source_results:
                        validated_results = validate_and_deduplicate_frequencies(all_source_results)
                        page_rows.extend(validated_results)
                        logger.info(f"Total unique validated results: {len(validated_results)}")
                    
                    # Fallback to RadioReference ZIP search
                    if not page_rows:
                        zip_search = f'https://www.radioreference.com/db/search/?zip={zip_code}'
                        page_rows = list(fetch_freqs_for_page(zip_search))
                        
                if not page_rows:
                    fetch_errors.append((label, u, 'No repeater rows returned from any source'))
                filtered_rows = []
                for tup in page_rows:
                    if len(tup) >= 6:
                        name, f, tone, duplex_hint, offset_hint, row_text = tup[0], tup[1], tup[2], tup[3], tup[4], tup[5]
                    elif len(tup) == 5:
                        name, f, tone, duplex_hint, offset_hint = tup[0], tup[1], tup[2], tup[3], tup[4]
                        row_text = tup[0]
                    else:
                        name, f, tone = tup[0], tup[1], tup[2]
                        duplex_hint, offset_hint = (None, None)
                        row_text = tup[0]
                    band_label = None
                    try:
                        if 'Emergency' in sel_bands:
                            lname_check = (row_text or name or '').lower()
                            emergency_keywords = [
                                'dispatch', 'police', 'pd', 'sheriff', 'law', 'tac', 'tactical',
                                'fire', 'fd', 'fireground', 'fire ground', 'fire dispatch', 'fire-tac',
                                'ems', 'ems-tac', 'ambulance', 'medical', 'emt',
                                'emergency', 'public safety',
                                'citywide', 'city-wide', 'city wide', 'c/w', 'cw',
                                'mutual aid', 'operations', 'rescue', 'command', 'engine',
                            ]
                            if any(kw in lname_check for kw in emergency_keywords):
                                band_label = 'Emergency'
                            else:
                                for lo, hi in BAND_RANGES.get('Emergency', []):
                                    try:
                                        if lo <= float(f) <= hi:
                                            band_label = 'Emergency'
                                            break
                                    except Exception:
                                        continue

                        if not band_label:
                            for band in sel_bands:
                                if band == 'Emergency':
                                    continue
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

                        if not band_label and 'Emergency' in sel_bands:
                            lname = (row_text or name or '').lower()
                            detected_protocol = None
                            emergency_keywords = [
                                'dispatch', 'police', 'fire', 'fire dept', 'fire department',
                                'sheriff', 'ems', 'ambulance', 'emergency', 'public safety',
                                'citywide', 'city-wide', 'city wide',
                            ]
                            p25_tokens = ['p25', 'project 25']
                            edacs_tokens = ['edacs']
                            other_digital = ['dmr', 'nxdn', 'tdma', 'trunk', 'trunking', 'digital']

                            match = False
                            for kw in emergency_keywords:
                                if kw in lname:
                                    match = True
                                    break

                            if not match:
                                for lo, hi in BAND_RANGES.get('Emergency', []):
                                    try:
                                        if lo <= float(f) <= hi:
                                            match = True
                                            break
                                    except Exception:
                                        continue

                            selected_emergency_types = [et for et, var in emergency_filter_vars.items() if var.get()]
                            if not selected_emergency_types:
                                selected_emergency_types = list(EMERGENCY_TYPE_KEYWORDS.keys())
                            if match:
                                type_tokens = []
                                for et in selected_emergency_types:
                                    type_tokens.extend(EMERGENCY_TYPE_KEYWORDS.get(et, []))
                                if not any(token in lname for token in type_tokens):
                                    match = False

                            if match and cust_level in ('Advanced', 'High Quality'):
                                if any(t in lname for t in p25_tokens):
                                    detected_protocol = 'P25'
                                elif any(t in lname for t in edacs_tokens):
                                    detected_protocol = 'EDACS'
                                if any(t in lname for t in other_digital) and not model_obj.get('supports_digital_mode'):
                                    match = False

                            if detected_protocol:
                                if detected_protocol == 'P25' and not model_obj.get('supports_p25'):
                                    match = False
                                if detected_protocol == 'EDACS' and not model_obj.get('supports_edacs'):
                                    match = False

                            if match:
                                band_label = 'Emergency'
                                if detected_protocol:
                                    name = f"{name} [{detected_protocol}]"
                    except Exception:
                        pass
                    if not band_label:
                        continue
                    if band_label == 'Emergency' and not is_analog_emergency_channel(name, row_text, label):
                        continue
                    filtered_rows.append({'Name': name, 'Frequency': f, 'Duplex': None, 'Tone': tone, 'Comment': label, 'Band': band_label, 'duplex_hint': duplex_hint, 'offset_hint': offset_hint, 'RawText': row_text})
                page_results.append({'zip': zip_code, 'label': label, 'rows': filtered_rows})
            except Exception as exc:
                fetch_errors.append((label, u, str(exc)))

        rows = []
        zip_order = []
        zip_rows = {}
        for pr in page_results:
            if pr['zip'] is None:
                continue
            if pr['zip'] not in zip_rows:
                zip_rows[pr['zip']] = []
                zip_order.append(pr['zip'])
            zip_rows[pr['zip']].extend(pr['rows'])

        if max_channels and zip_order:
            reserved_noaa = 10 if 'NOAA' in sel_bands else 0
            remaining_slots = max(max_channels - reserved_noaa, 0)
            quality_target = selected_source == 'RadioReference' and len(zip_order) == 1 and cust_level in ('Advanced', 'High Quality')
            if quality_target:
                target_capacity = max(int(max_channels * 0.8), 1)
                remaining_slots = min(remaining_slots, target_capacity)
            rows.extend(select_zip_rows_with_fair_limit(zip_rows, remaining_slots, zip_order, prioritize_quality=quality_target, model_info=model_obj))
            for pr in page_results:
                if pr['zip'] is None:
                    rows.extend(pr['rows'])
        else:
            rows = [row for pr in page_results for row in pr['rows']]

        if fetch_errors and show_warnings:
            warning_text = 'Some RadioReference pages could not be fetched or parsed.\n'
            warning_text += 'Only fixed-band NOAA/MURS/FRS-GMRS rows may be available.\n\n'
            warning_text += '\n'.join(f'{label}: {err}' for label, _, err in fetch_errors[:5])
            if len(fetch_errors) > 5:
                warning_text += f'\n...and {len(fetch_errors)-5} more.'
            messagebox.showwarning('RadioReference fetch warning', warning_text)

        if 'NOAA' in sel_bands:
            for entry in NOAA_FREQS:
                name, f, tone, raw = entry
                rows.append({'Name': name or f'NOAA {f}', 'Frequency': f, 'Duplex': '', 'Tone': tone or '', 'Comment': 'Weather', 'Band': 'NOAA'})

        if 'MURS' in sel_bands:
            for entry in MURS_FREQS:
                name, f, tone, raw = entry
                rows.append({'Name': name or f'MURS {f}', 'Frequency': f, 'Duplex': '', 'Tone': tone or '', 'Comment': 'MURS', 'Band': 'MURS'})

        if 'FRS/GMRS' in sel_bands:
            for entry in FRS_GMRS_FREQS:
                name, f, duplex, tone, raw = entry
                rows.append({'Name': name or f'Channel {f}', 'Frequency': f, 'Duplex': duplex or '', 'Tone': tone or '', 'Comment': 'FRS/GMRS', 'Band': 'FRS/GMRS'})

        # Add local calling frequencies when Local Calling Frequencies is enabled
        calling_freq_rows = []
        if scope_only_var.get() and any(band in sel_bands for band in ['2m', '70cm', '1.25m']):
            for entry in LOCAL_CALLING_FREQS:
                name, f, duplex, tone = entry
                # Determine which band this frequency belongs to
                try:
                    freq_float = float(f)
                    if 144.0 <= freq_float <= 148.0 and '2m' in sel_bands:
                        calling_freq_rows.append({'Name': name, 'Frequency': f, 'Duplex': duplex, 'Tone': tone, 'Comment': 'Local Calling', 'Band': '2m'})
                    elif 420.0 <= freq_float <= 450.0 and '70cm' in sel_bands:
                        calling_freq_rows.append({'Name': name, 'Frequency': f, 'Duplex': duplex, 'Tone': tone, 'Comment': 'Local Calling', 'Band': '70cm'})
                    elif 222.0 <= freq_float <= 225.0 and '1.25m' in sel_bands:
                        calling_freq_rows.append({'Name': name, 'Frequency': f, 'Duplex': duplex, 'Tone': tone, 'Comment': 'Local Calling', 'Band': '1.25m'})
                except Exception:
                    continue

        if model_obj.get('frequency_ranges'):
            original_count = len(rows)
            rows = [r for r in rows if model_supports_frequency(model_obj, r.get('Frequency', ''))]
            if show_warnings and len(rows) != original_count:
                removed = original_count - len(rows)
                messagebox.showwarning(
                    'Model Frequency Filter',
                    f'{removed} channel(s) were removed because they are outside the selected model ({model_obj.get("name")}) frequency range.'
                )

        # Add calling frequencies to the beginning of each ZIP code group
        if calling_freq_rows and zip_order:
            # Insert calling frequencies at the beginning of each ZIP code's results
            for zip_code in zip_order:
                if zip_code in zip_rows:
                    # Insert calling frequencies at the start of this ZIP's rows
                    zip_rows[zip_code] = calling_freq_rows + zip_rows[zip_code]
            
            # Rebuild rows list with calling frequencies properly positioned and ZIP separators
            rows = []
            for i, zip_code in enumerate(zip_order):
                if zip_code in zip_rows:
                    # Add ZIP code separator (except for first ZIP)
                    if i > 0:
                        rows.append({
                            'Name': f'--- ZIP Code {zip_code} ---',
                            'Frequency': '',
                            'Duplex': '',
                            'Tone': '',
                            'Comment': 'ZIP Code Separator',
                            'Band': 'Separator'
                        })
                    rows.extend(zip_rows[zip_code])

        rows = _dedupe_export_rows(rows)

        def numeric_frequency(value):
            try:
                return float(value)
            except Exception:
                return 0.0

        selected_emergency_types = [et for et, var in emergency_filter_vars.items() if var.get()]

        # Sort by band order, then by frequency (calling frequencies already at top)
        band_order = {b: i for i, b in enumerate(sel_bands)}
        def sort_key(r):
            # Calling frequencies stay at top (already positioned)
            if r.get('Comment') == 'Local Calling':
                return (0, numeric_frequency(r.get('Frequency', 0)))
            # Then sort by band order
            band_order_val = band_order.get(r.get('Band'), 999)
            return (1, band_order_val, numeric_frequency(r.get('Frequency', 0)))
        
        rows.sort(key=sort_key)

        deduped = []
        seen_keys = set()
        for r in rows:
            key = (
                r.get('Band', ''),
                str(r.get('Frequency', '')).strip(),
                (r.get('Name') or '').strip().lower(),
                (r.get('Tone') or '').strip(),
                (r.get('Duplex') or '').strip(),
                (r.get('Offset') or '').strip(),
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(r)
        rows = deduped

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
            if not tone_text or not str(tone_text).strip():
                return ('', '0.0', '0.0')
            t = str(tone_text).strip()
            if t.upper() == 'CSQ':
                return ('CSQ', '0.0', '0.0')
            m = re.search(r"([0-9]+\.?[0-9]*)", t)
            if m:
                try:
                    valf = float(m.group(1))
                except Exception:
                    return ('', '0.0', '0.0')
                if not (50.0 <= valf <= 260.0):
                    return ('', '0.0', '0.0')
                val = f"{valf:.1f}"
                return ('Tone', val, val)
            return ('', '0.0', '0.0')

        df_rows = []
        for r in rows:
            name = r.get('Name','')
            raw_text = r.get('RawText','') or ''
            freq = r.get('Frequency','')
            band = r.get('Band','')
            
            # Skip separator rows
            if band == 'Separator':
                continue
                
            duplex = '+' if (isinstance(freq, (int,float)) and freq >= 147) else '-' if isinstance(freq, (int,float)) and freq < 147 else ''
            offset = compute_offset_local(freq) if duplex == '+' else ''
            tone_label, rTone, cTone = parse_tone_local(r.get('Tone',''))
            dtcs = '023' if rTone else ''
            dtcs_pol = 'NN' if rTone else ''
            if not rTone and band not in ('NOAA', 'MURS', 'FRS/GMRS', '2m', '70cm', '1.25m', 'Emergency'):
                continue
            if raw_text and raw_text not in name and (not name or len(name) <= 4):
                name = f"{name} {raw_text}".strip()
            comment = r.get('Comment','')
            band_display = band
            if band in ('2m', '70cm', '1.25m'):
                band_display = 'Ham'
            if band and comment:
                comment = f"[{band_display}] {comment}"
            elif band:
                comment = f"[{band_display}]"
            if raw_text and raw_text not in comment and raw_text not in name:
                comment = f"{comment} | {raw_text}".strip(' |')
            if band == 'Emergency':
                lname = (name or '').lower()
                combined_text = ' '.join(filter(None, [name or '', comment or '', raw_text or ''])).lower()
                protocol = None
                
                # Check for digital protocols in name, comment, or raw text
                if re.search(r'\[(P25|EDACS)\]$', name):
                    protocol = re.search(r'\[(P25|EDACS)\]$', name).group(1)
                elif 'd-star' in lname or 'dstar' in lname:
                    protocol = 'D-STAR'
                elif 'p25' in combined_text:
                    protocol = 'P25'
                elif 'c4fm' in combined_text or 'system fusion' in combined_text or 'fusion' in lname:
                    protocol = 'C4FM'
                    
                if protocol:
                    if cust_level not in ('Advanced', 'High Quality'):
                        continue
                    if protocol == 'P25' and not model_obj.get('supports_p25'):
                        continue
                    if protocol == 'EDACS' and not model_obj.get('supports_edacs'):
                        continue
                    if protocol == 'D-STAR' and not model_obj.get('supports_dstar'):
                        continue
                    if protocol == 'C4FM' and not model_obj.get('supports_digital_mode'):
                        continue
                else:
                    other_digital = ('dmr', 'nxdn', 'tdma', 'trunk', 'trunking', 'digital')
                    if any(d in lname for d in other_digital):
                        if not model_obj.get('supports_digital_mode') or cust_level not in ('Advanced', 'High Quality'):
                            continue
            skip_value = ''
            if scanner_mode_enabled and profile_var.get() == 'HamScan' and band in ('Emergency', 'NOAA'):
                skip_value = 'S'
            elif scanner_mode_enabled and profile_var.get() == 'Emergency Comms' and band in ('2m', '70cm', '1.25m', 'NOAA'):
                skip_value = 'S'
            elif scanner_mode_enabled and profile_var.get() == 'Traveler' and band == 'NOAA':
                skip_value = 'S'
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
                'TStep': preferences_data.get('step_size').get() if preferences_data.get('step_size') else 5,
                'Skip': skip_value,
                'Comment': comment,
                'Band': band,
            })

        try:
            import pandas as pd
            outdf = pd.DataFrame(df_rows)
            stats_df = outdf.copy()
            cols = ["Name","Frequency","Duplex","Offset","Tone","rToneFreq","cToneFreq","DtcsCode","DtcsPolarity","Mode","TStep","Skip","Comment"]
            for c in cols:
                if c not in outdf.columns:
                    outdf[c] = ''
            outdf = outdf[cols]
            outdf.index = [f"{i:03d}" for i in range(1, len(outdf)+1)]
            outdf.index.name = 'Location'
            exported_data['export_stats'] = _format_export_statistics(stats_df)
            exported_data['dataframe'] = outdf
            exported_data['row_count'] = len(outdf)
            exported_data['pages'] = pages
            max_channels = model_obj.get('max_channels')
            if max_channels and len(outdf) > max_channels:
                if show_warnings:
                    messagebox.showerror(
                        'Channel Capacity Exceeded',
                        f'The export contains {len(outdf)} channels, which exceeds the selected radio model\'s capacity of {max_channels} channels.\n'
                        'Reduce the selected bands, locations, or choose a higher-capacity radio model before exporting.'
                    )
                return None, None
            warn_limit_enabled = APP_SETTINGS.get('warn_channel_limit', {}).get('value', APP_SETTINGS.get('warn_channel_limit', {}).get('default', False))
            if warn_limit_enabled and max_channels and len(outdf) > max_channels:
                if show_warnings:
                    messagebox.showwarning(
                        'Channel Capacity Warning',
                        f'The export contains {len(outdf)} channels, which exceeds the selected radio model\'s capacity of {max_channels} channels.\n'
                        'Your radio may not be able to store all of them. Consider reducing the selected bands, locations, or choosing a higher-capacity radio model.'
                    )
            return outdf, pages
        except Exception as exc:
            if show_warnings:
                messagebox.showerror('Error', f'Failed to build export preview: {exc}')
            return None, None

    def open_preview_summary(df):
        if df is None or len(df) == 0:
            messagebox.showwarning('Preview', 'No export data available for preview.')
            return
        summary_win = tk.Toplevel(root)
        summary_win.title('Preview Summary')
        summary_win.geometry('700x500')
        summary_win.transient(root)
        summary_win.grab_set()
        counts = {}
        skip_counts = 0
        for _, row in df.iterrows():
            band = row.get('Comment', '') or 'Unknown'
            counts[band] = counts.get(band, 0) + 1
            if str(row.get('Skip', '')).upper() == 'S':
                skip_counts += 1
        lines = [f'Rows: {len(df)}', f'Skipped rows: {skip_counts}', '', 'Counts by comment/band:']
        for k, v in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
            lines.append(f'  {k}: {v}')
        txt = tk.Text(summary_win, wrap='word', font=('Courier', 10))
        txt.pack(fill='both', expand=True, padx=10, pady=10)
        txt.insert('end', '\n'.join(lines))
        txt.config(state='disabled')
        tk.Button(summary_win, text='Close', command=summary_win.destroy, width=10).pack(pady=10)

    def open_export_preview(df):
        if df is None or len(df) == 0:
            messagebox.showwarning('Preview', 'No export data available for preview.')
            return

        preview_win = tk.Toplevel(root)
        preview_win.title('Export Preview')
        preview_win.geometry('900x600')
        preview_win.transient(root)
        preview_win.grab_set()

        text_frame = tk.Frame(preview_win)
        text_frame.pack(fill='both', expand=True)

        xscrollbar = ttk.Scrollbar(text_frame, orient='horizontal')
        xscrollbar.pack(side='bottom', fill='x')
        scrollbar = ttk.Scrollbar(text_frame, orient='vertical')
        scrollbar.pack(side='right', fill='y')
        txt = tk.Text(text_frame, wrap='none', yscrollcommand=scrollbar.set, xscrollcommand=xscrollbar.set, font=('Courier', 10))
        txt.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=txt.yview)
        xscrollbar.config(command=txt.xview)

        def _preview_mousewheel(event):
            delta = 0
            if hasattr(event, 'delta') and event.delta:
                delta = int(event.delta / 120)
            elif event.num == 4:
                delta = 1
            elif event.num == 5:
                delta = -1
            if event.state & 0x0001:  # Shift held
                txt.xview_scroll(-delta, 'units')
            else:
                txt.yview_scroll(-delta, 'units')
            return 'break'

        txt.bind('<MouseWheel>', _preview_mousewheel)
        txt.bind('<Shift-MouseWheel>', _preview_mousewheel)
        txt.bind('<Button-4>', _preview_mousewheel)
        txt.bind('<Button-5>', _preview_mousewheel)
        txt.bind('<Shift-Button-4>', _preview_mousewheel)
        txt.bind('<Shift-Button-5>', _preview_mousewheel)

        try:
            preview_text = df.to_string(max_rows=200, max_cols=12)
        except Exception:
            preview_text = str(df.head(200))
        txt.insert('end', preview_text)
        txt.config(state='disabled')

        def open_pdf_preview():
            try:
                import tempfile
                html = '<html><head><meta charset="utf-8"><style>body{font-family:monospace;}</style></head><body>'
                html += '<h2>FreqFinder Export Preview</h2>'
                html += df.to_html(border=1, index=True)
                html += '<p>Use your browser Print dialog to save to PDF.</p>'
                html += '</body></html>'
                tmp = tempfile.NamedTemporaryFile('w', suffix='.html', delete=False, encoding='utf-8')
                tmp.write(html)
                tmp.close()
                import webbrowser
                webbrowser.open(f'file://{tmp.name}')
            except Exception as e:
                messagebox.showerror('Preview', f'Failed to open print preview: {e}')

        def save_preview_as_csv():
            try:
                if df is None or len(df) == 0:
                    messagebox.showwarning('Preview', 'No export data available to save.')
                    return
                initial_dir = DEFAULT_SAVE_DIR if os.path.isdir(DEFAULT_SAVE_DIR) else None
                save_path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV files','*.csv'),('All files','*.*')], initialdir=initial_dir, initialfile='FreqFinder_Preview.csv', title='Save Preview CSV as')
                if not save_path:
                    return
                write_export_csv(save_path, df)
                exported_data['preview_csv_path'] = save_path
                messagebox.showinfo('Saved', f'Preview CSV saved to {save_path}')
                verify_export_file_hashes()
            except Exception as e:
                messagebox.showerror('Error', f'Failed saving preview CSV: {e}')

        btn_frame = tk.Frame(preview_win)
        btn_frame.pack(fill='x', pady=8)
        tk.Button(btn_frame, text='Save Preview CSV', command=save_preview_as_csv, width=16).pack(side='left', padx=10)
        tk.Button(btn_frame, text='Print Preview', command=open_pdf_preview, width=14).pack(side='left', padx=10)
        tk.Button(btn_frame, text='Close', command=preview_win.destroy, width=10).pack(side='right', padx=10)

    def on_quick_export():
        if exporting_flag.get('running'):
            messagebox.showwarning('Quick Export', 'Export in progress — please wait until it completes.')
            return
        df, pages = build_export_dataframe(show_warnings=True)
        if df is None or len(df) == 0:
            return
        exported_data['dataframe'] = df
        exported_data['row_count'] = len(df)
        exported_data['pages'] = pages or {}

        default_path = exported_data.get('last_export_path') or None
        if default_path and os.path.isdir(os.path.dirname(default_path)):
            save_path = default_path
        else:
            default_name = _get_quick_export_default_filename()
            initial_dir = DEFAULT_SAVE_DIR if os.path.isdir(DEFAULT_SAVE_DIR) else None
            save_path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV files','*.csv'),('All files','*.*')], initialdir=initial_dir, initialfile=default_name, title='Quick Export CSV as')
            if not save_path:
                return

        try:
            outdf = exported_data['dataframe']
            write_export_csv(save_path, outdf)
            exported_data['quick_export_path'] = save_path
            exported_data['last_export_path'] = save_path
            update_status_bar(exported_rows=len(outdf), profile_name=profile_var.get(), last_path=save_path)
            messagebox.showinfo('Quick Export', f'Wrote {len(outdf)} rows to {save_path}')
            verify_export_file_hashes()
        except Exception as e:
            messagebox.showerror('Quick Export', f'Failed to save quick export: {e}')

    def on_preview():
        df, pages = build_export_dataframe(show_warnings=True)
        if df is None or len(df) == 0:
            return
        if preferences_data.get('preview_mode').get() == 0:
            open_preview_summary(df)
        else:
            open_export_preview(df)

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
    export_row = model_options_row + 1
    root.grid_rowconfigure(export_row, weight=0)
    
    export_btn = tk.Button(root, text='Export CSV', command=on_export, bg='#4CAF50', fg='white', height=2, font=('Arial', 11, 'bold'))
    export_btn.grid(row=export_row, column=0, columnspan=2, pady=12, sticky='ew', padx=8)
    ToolTip(export_btn, 'Export scraped frequencies to CHIRP CSV file\nfor programming into your radio')

    quick_export_btn = tk.Button(root, text='Quick Export', command=lambda: on_quick_export(), bg='#FF9800', fg='white', height=2, font=('Arial', 11, 'bold'))
    quick_export_btn.grid(row=export_row, column=2, pady=12, sticky='ew', padx=8)
    ToolTip(quick_export_btn, 'Quick-export the current CSV using the last export location or choose a save path')

    preview_btn = tk.Button(root, text='Preview/Print', command=on_preview, bg='#1976D2', fg='white', height=2, font=('Arial', 11, 'bold'))
    preview_btn.grid(row=export_row, column=3, pady=12, sticky='ew', padx=8)
    ToolTip(preview_btn, 'Preview the generated export and open a print-friendly PDF preview in your browser')

    status_var = tk.StringVar(value='Ready')
    status_bar = tk.Frame(root, bd=1, relief='sunken')
    status_bar.grid(row=export_row+1, column=0, columnspan=4, sticky='ew', padx=8, pady=(0,4))
    status_label = tk.Label(status_bar, textvariable=status_var, anchor='w', font=('Arial', 9))
    status_label.pack(fill='x', padx=6, pady=4)

    def update_status_bar(exported_rows=None, profile_name=None, last_path=None):
        parts = ['Ready']
        if profile_name:
            parts.append(f'Profile: {profile_name}')
        if exported_rows is not None:
            parts.append(f'Last export rows: {exported_rows}')
        if last_path:
            parts.append(f'Last path: {last_path}')
        status_var.set(' | '.join(parts))

    update_status_bar()

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
        ignored_band_tokens = []
        for t in tokens:
            if is_band_token(t):
                ignored_band_tokens.append(t)
                continue
            if t.startswith('http://') or t.startswith('https://'):
                label = get_location_from_url(t) or t
                pages[label] = t
            else:
                # map ZIP to county page
                zip_pages = map_zips_to_counties([t])
                pages.update(zip_pages)
        if ignored_band_tokens:
            print(f"NOTE: Ignoring band tokens passed to --pages: {', '.join(ignored_band_tokens)}")
    else:
        if args.prompt:
                pages, prompt_bands = get_pages_from_user()
                if prompt_bands:
                    print(f"Selected bands from prompt: {', '.join(prompt_bands)}")
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

    explicit_cli = bool(
        args.pages or args.prompt or args.qrz_stub or args.source == 'radio_browser' or args.include_broadcast
    )

    if args.gui:
        try:
            launch_gui_and_run(DEFAULT_PAGES, args.output)
            return
        except Exception as e:
            print(f'GUI startup failed ({e}); exiting. Use --pages to run in CLI mode explicitly.')
            return

    if gui_session_available():
        try:
            launch_gui_and_run(DEFAULT_PAGES, args.output)
            return
        except Exception as e:
            if explicit_cli:
                print(f'GUI startup failed ({e}); running in CLI mode')
            else:
                print(f'GUI startup failed ({e}); exiting because no CLI request was made.')
                return
    else:
        if not explicit_cli:
            print('GUI not available: tkinter is not installed in this Python environment; no CLI request was provided. Exiting.')
            return
        print('GUI not available: tkinter is not installed in this Python environment; running in CLI mode')
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
        if not tone_text or not str(tone_text).strip():
            return ('', '', '')
        t = str(tone_text).strip()
        if t.upper() == 'CSQ':
            return ('', '', '')
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
        return ('', '', '')

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
