# chirp_scraper.py
# TX is ENABLED on repeaters via Duplex +/-
#
# Note: This script uses a small local index file `radioref.csv` which maps
# RadioReference CTID pages (county/city names) to numeric IDs. The helper
# script `make_radioref_list.py` compiles that index by crawling
# https://www.radioreference.com/db/browse/ctid/<id>/ham pages and writing
# `radioref.csv`. If `radioref.csv` is missing or you want to refresh RadioReference
# data, run `make_radioref_list.py` before using this program.


import os
import sys
import subprocess

def _ensure_project_venv_and_requirements():
    here = os.path.dirname(os.path.abspath(__file__))
    venv_dir = os.path.join(here, '.venv')
    # Choose the platform-specific virtualenv python path
    if os.name == 'nt':
        venv_py = os.path.join(venv_dir, 'Scripts', 'python.exe')
    else:
        venv_py = os.path.join(venv_dir, 'bin', 'python')
    reqs = os.path.join(here, 'requirements.txt')

    # Create venv if missing
    if not os.path.exists(venv_py):
        print('Creating virtual environment...')
        subprocess.check_call([sys.executable, '-m', 'venv', venv_dir])


    # Install requirements if needed
    need_reexec = False
    try:
        import pandas, bs4, requests
    except ImportError:
        print('Installing required Python packages...')
        subprocess.check_call([venv_py, '-m', 'pip', 'install', '--upgrade', 'pip'])
        if os.path.exists(reqs):
            subprocess.check_call([venv_py, '-m', 'pip', 'install', '-r', reqs])
        else:
            subprocess.check_call([venv_py, '-m', 'pip', 'install', 'pandas', 'requests', 'beautifulsoup4'])
        need_reexec = True

    # Always re-exec in venv after installing requirements, or if not already in venv
    if need_reexec or os.path.realpath(sys.executable) != os.path.realpath(venv_py):
        os.execv(venv_py, [venv_py] + sys.argv)

_ensure_project_venv_and_requirements()

import re
import sys
import os
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
            # If we still don't have a key, create the built-in encrypted key and use it
            if RR_API_KEY is None:
                try:
                    import secrets
                    builtin = 'fcb8749c-f4c9-11f0-bb32-0ef97433b5f9'
                    p = secrets.token_urlsafe(24)
                    _rr_api.encrypt_api_key(builtin, p, outpath=enc_path)
                    try:
                        with open(passfile, 'w', encoding='utf-8') as pf:
                            pf.write(p)
                        os.chmod(passfile, 0o600)
                    except Exception:
                        pass
                    os.environ['RR_API_PASS'] = p
                    RR_API_KEY = builtin
                except Exception:
                    RR_API_KEY = None
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
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"}
    resp = requests.get(url, headers=headers, timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")
    out = []
    # Radioreference uses tables with class 'rrdbTable' for frequency lists
    for table in soup.select("table.rrdbTable"):
        for tr in table.select("tbody tr"):
            td = tr.find_all("td")
            if len(td) < 3:
                continue
            # primary frequency is in first column
            ftext = td[0].text.strip()
            try:
                f = float(ftext)
            except Exception:
                # skip rows without numeric frequency
                continue
            if not valid_freq(f):
                continue
            # default extraction: callsign (col 2), tone (col 4), description (col 7)
            callsign = td[2].text.strip() if len(td) > 2 else ""
            tone = td[4].text.strip() if len(td) > 4 else ""
            desc = ""
            for idx in (7, 6, 3):
                if idx < len(td):
                    txt = td[idx].text.strip()
                    if txt:
                        desc = txt
                        break
            # prefer callsign, otherwise description
            name = callsign or desc or ""
            # try to parse duplex/offset hints from the remaining cells (skip first col which is freq)
            duplex_hint = None
            offset_hint = None
            try:
                other_texts = ' '.join(td[i].text.strip() for i in range(1, len(td)))
                # look for explicit plus/minus tokens indicating duplex
                if re.search(r'\b\+\b', other_texts) or re.search(r'\bplus\b', other_texts, re.I):
                    duplex_hint = '+'
                elif re.search(r'\b\-\b', other_texts) or re.search(r'\bminus\b', other_texts, re.I):
                    duplex_hint = '-'
                # find numeric offsets like 0.600 or 5.000 (common RR format)
                nums = re.findall(r'([0-9]+\.[0-9]+)', other_texts)
                for n in nums:
                    try:
                        nv = float(n)
                    except Exception:
                        continue
                    if abs(nv - 0.6) < 0.001 or abs(nv - 5.0) < 0.01 or abs(nv - 0.600) < 0.001 or abs(nv - 5.000) < 0.01:
                        offset_hint = nv
                        # try to find sign near the number
                        m = re.search(r'([\+\-])\s*' + re.escape(n), other_texts)
                        if m:
                            duplex_hint = m.group(1)
                        break
            except Exception:
                pass

            out.append((name, f, tone, duplex_hint, offset_hint))
    return out
    


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
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200 and 'rrdbTable' in resp.text:
                return parse_rr_html(resp.text)
    except Exception:
        pass
    # fallback
    return scrape_rr(url)

def get_pages_from_user():
    """Get a dict of {label: url} from the user.

    Supports:
    - GUI prompt (Tk) when available and DISPLAY set
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
    # On Windows, DISPLAY is not used; allow Tk when available on Windows
    if _TK_AVAILABLE and (os.name == 'nt' or os.environ.get("DISPLAY")):
        try:
            root = tk.Tk()
            # set a friendly title instead of the default 'Tk'
            try:
                root.title('ChirpScrape')
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
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
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
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"}
    zip_url = f"https://www.radioreference.com/db/browse/zip/{zip_code}/ham"
    try:
        r = requests.get(zip_url, headers=headers, timeout=10)
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
        place = requests.get(f'http://api.zippopotam.us/us/{zip_code}', timeout=8).json()
        places = place.get('places', [])
        if places:
            lat = places[0].get('latitude')
            lon = places[0].get('longitude')
            state = places[0].get('state') or place.get('state')
            # reverse geocode with Nominatim to get county
            if lat and lon:
                nom = requests.get(f'https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}', headers={'User-Agent':'chirp-scraper'}, timeout=8).json()
                addr = nom.get('address', {})
                county = addr.get('county')
                state_name = addr.get('state') or state
                if county and state_name:
                    # search RadioReference for county page
                    rr_search = requests.get('https://www.radioreference.com/search/', params={'q': f"{county} {state_name}"}, headers=headers, timeout=10)
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


def map_zips_to_counties(zips):
    """Map a list of ZIP strings to unique county pages on RadioReference.

    Returns dict {label: url}.
    """
    pages = {}
    for z in zips:
        lbl, url = get_county_from_zip(z)
        if lbl is None:
            # use zip page as fallback label
            lbl = f'ZIP {z}'
        # dedupe by URL
        if url not in pages.values():
            pages[lbl] = url
    return pages


def launch_gui_and_run(default_pages, output_path):
    import tkinter as tk
    from tkinter import ttk, messagebox
    import webbrowser
    from tkinter import filedialog

    root = tk.Tk()
    # set main window title
    try:
        root.title('ChirpScrape')
    except Exception:
        root.title('CHIRP RR Scraper')

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
    # File menu with Exit
    filemenu = tk.Menu(menubar, tearoff=0)
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
                webbrowser.open('https://github.com/Drizztdowhateva/Chirp_Scrape')
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
        webbrowser.open('https://github.com/Drizztdowhateva/Chirp_Scrape')

    contactmenu.add_command(label='Donations', command=open_donations)
    contactmenu.add_command(label='GitHub Project', command=open_github)
    helpmenu.add_cascade(label='Contact', menu=contactmenu)
    # SOAP Debug submenu
    def open_soap_debug():
        dlg = tk.Toplevel(root)
        dlg.title('SOAP Debug')
        dlg.geometry('800x500')
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
                messagebox.showinfo('API', f'Built-in key encrypted and saved to {enc_path}')
            except Exception as e:
                messagebox.showerror('API', f'Failed to encrypt built-in key: {e}')
        else:
            messagebox.showwarning('API', f'Unknown API action: {selection}')

    # Add API menu to the menubar (commands mirror previous dropdown)
    apimenu = tk.Menu(menubar, tearoff=0)
    apimenu.add_command(label='Enter API key...', command=lambda: handle_api_choice('Enter API key...'))
    apimenu.add_command(label='Use built-in (encrypted)', command=lambda: handle_api_choice('Use built-in (encrypted)'))
    menubar.add_cascade(label='API', menu=apimenu)

    # Attach Help menu after API so order is File -> API -> Help
    menubar.add_cascade(label='Help', menu=helpmenu)
    root.config(menu=menubar)

    # Make window wider to fit content and provide an area on the right for a QR image
    root.geometry('1100x700')
    root.resizable(True, True)
    root.grid_columnconfigure(3, weight=1)

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
            img_label.grid(row=0, column=3, rowspan=12, padx=12, pady=8, sticky='n')
    except Exception:
        pass

    def show_donation_dialog():
        dlg = tk.Toplevel(root)
        dlg.title('Support ChirpScrape')
        dlg.geometry('420x160')
        dlg.grab_set()
        tk.Label(dlg, text="Please help pay for the numerous accounts, interfaces and time that I have spent on ChirpScrape.", wraplength=400, justify='left', font=(None, 11)).pack(padx=18, pady=(18, 10))
        btn_frame = tk.Frame(dlg)
        btn_frame.pack(pady=(0, 16))

        def close_dialog():
            dlg.destroy()

        def open_donate():
            close_dialog()
            open_donations()

        tk.Button(btn_frame, text="Not Now", width=12, command=close_dialog).pack(side='left', padx=10)
        tk.Button(btn_frame, text="Donate", width=12, command=open_donate).pack(side='left', padx=10)

    # Show donation dialog on program open
    root.after(100, show_donation_dialog)

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
                pr = requests.get(f'http://api.zippopotam.us/us/{v}', timeout=6)
                if pr.status_code == 200:
                    pj = pr.json()
                    places = pj.get('places', [])
                    if places:
                        lat = places[0].get('latitude')
                        lon = places[0].get('longitude')
                        if lat and lon:
                            nom = requests.get(f'https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}', headers={'User-Agent':'chirp-scraper'}, timeout=8).json()
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
        tk.Label(root, text=f'Zip Code {i}:').grid(row=i-1, column=0, sticky='e')
        ent = tk.Entry(root, textvariable=iv, width=28)
        ent.grid(row=i-1, column=1, sticky='w')
        # resolved label to the right
        tk.Label(root, textvariable=resolved_labels[i-1], width=40, anchor='w').grid(row=i-1, column=2, sticky='w')
        # trace changes
        iv.trace_add('write', lambda *_i, idx=i-1: resolve_input(idx))

    # Bands checkbuttons and listbox - place below the input boxes and stack vertically
    start_row = len(input_vars)
    tk.Label(root, text='Available Bands:').grid(row=start_row, column=0, padx=8, sticky='w')
    band_vars = {}
    band_listbox = tk.Listbox(root, height=len(BAND_RANGES))
    band_listbox.grid(row=start_row+1, column=1, rowspan=len(BAND_RANGES), sticky='n', padx=8, pady=4)

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

    tk.Button(root, text='Up', command=move_up).grid(row=start_row+1+len(BAND_RANGES), column=1, sticky='w', padx=8)
    tk.Button(root, text='Down', command=move_down).grid(row=start_row+1+len(BAND_RANGES), column=1, sticky='e', padx=8)

    # Export button (centered at bottom)
    def on_export():
        pages = {}
        # Require at least one ZIP code and one band selected
        zip_present = any(re.match(r'^\d{5}$', iv.get().strip() or '') for iv in input_vars)
        band_selected = any(v.get() for v in band_vars.values())
        if not zip_present or not band_selected:
            messagebox.showerror('Error', 'Must have at least one ZIP code and at least one band selected')
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
                    pr = requests.get(f'http://api.zippopotam.us/us/{u}', timeout=6)
                    if pr.status_code == 200:
                        pj = pr.json()
                        places = pj.get('places', [])
                        if places:
                            lat = places[0].get('latitude')
                            lon = places[0].get('longitude')
                            if lat and lon:
                                nom = requests.get(f'https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}', headers={'User-Agent':'chirp-scraper'}, timeout=8).json()
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
            return

        # run scraping and filter by selected bands
        rows = []
        for c, u in pages.items():
            for tup in fetch_freqs_for_page(u):
                    # unpack flexible return (name,freq,tone[,duplex_hint,offset_hint])
                    if len(tup) >= 5:
                        name, f, tone, duplex_hint, offset_hint = tup[0], tup[1], tup[2], tup[3], tup[4]
                    else:
                        name, f, tone = tup[0], tup[1], tup[2]
                        duplex_hint, offset_hint = (None, None)
                    # determine which band this frequency belongs to (first matching selected band)
                    band_label = None
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
            # Remove scanned entries that lack an rTone value. Preserve fixed band lists.
            if not rTone and band not in ('NOAA', 'MURS', 'FRS/GMRS'):
                continue
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
                'Skip': '',
                'Comment': r.get('Comment','')
            })

        import pandas as pd
        outdf = pd.DataFrame(df_rows)
        # ensure columns
        cols = ["Name","Frequency","Duplex","Offset","Tone","rToneFreq","cToneFreq","DtcsCode","DtcsPolarity","Mode","TStep","Skip","Comment"]
        for c in cols:
            if c not in outdf.columns:
                outdf[c] = ''
        outdf = outdf[cols]
        outdf.index = range(1, len(outdf)+1)
        outdf.index.name = 'Location'
        # Ask user where to save the CSV
        initial = output_path or 'chirp_output.csv'
        save_path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV files','*.csv'),('All files','*.*')], initialfile=initial, title='Save CSV as')
        if not save_path:
            return
        outdf.to_csv(save_path)
        messagebox.showinfo('Done', f'Wrote {len(outdf)} rows to {save_path}')

    # compute export row and place button centered across columns
    export_row = start_row+1+len(BAND_RANGES)+4
    root.grid_rowconfigure(export_row, weight=0)
    tk.Button(root, text='Export CSV', command=on_export, bg='#4CAF50', fg='white').grid(row=export_row, column=0, columnspan=4, pady=12)

    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description="Scrape RadioReference ham pages and produce CHIRP CSV")
    parser.add_argument('--pages', '-p', nargs='+', help='ZIP codes or Radioreference URLs (space separated)')
    parser.add_argument('--output', '-o', default='chirp_output.csv', help='Output CSV file')
    # GUI is the default; removed '--no-gui' option per request
    parser.add_argument('--prompt', action='store_true', help='Force interactive prompt for pages')
    parser.add_argument('--callsign-col', type=int, default=2, help='Column index for callsign/license (0-based)')
    parser.add_argument('--desc-col', type=int, default=7, help='Preferred column index for description (0-based)')
    parser.add_argument('--tone-col', type=int, default=4, help='Column index for tone (0-based)')
    parser.add_argument('--gui', action='store_true', help='Launch GUI to enter ZIPs and select bands')
    args = parser.parse_args()

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

    # GUI is default when available (Tkinter + DISPLAY). Otherwise run CLI.
    # Allow GUI on Windows without DISPLAY
    if _TK_AVAILABLE and (os.name == 'nt' or os.environ.get('DISPLAY')):
        launch_gui_and_run(DEFAULT_PAGES, args.output)
        return
    if not _TK_AVAILABLE or not os.environ.get('DISPLAY'):
        print('GUI not available; running in CLI mode')
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
    for n,f in NOAA_FREQS:
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
    for _, r in df.iterrows():
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
