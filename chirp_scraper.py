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

VALID_BANDS = [(136.0,174.0),(400.0,520.0)]

NOAA_FREQS = [
    ("NOAA WX 1",162.400),("NOAA WX 2",162.425),("NOAA WX 3",162.450),
    ("NOAA WX 4",162.475),("NOAA WX 5",162.500),("NOAA WX 6",162.525),
    ("NOAA WX 7",162.550)
]

DEFAULT_PAGES = {
    "Cook County, Illinois": "https://www.radioreference.com/db/browse/ctid/606/ham",
}

# Band definitions for GUI selection and filtering (ranges in MHz)
BAND_RANGES = {
    'NOAA': [(162.4, 162.55)],
    'MURS': [(151.82, 154.6)],
    'GMRS': [(462.0, 467.0)],
    'Simplex': [(136.0, 174.0), (400.0, 520.0)],
    'Repeaters': [(136.0, 174.0), (400.0, 520.0)],
}

def valid_freq(f):
    return any(lo<=f<=hi for lo,hi in VALID_BANDS)

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
    if _TK_AVAILABLE and os.environ.get("DISPLAY"):
        try:
            root = tk.Tk()
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

    root = tk.Tk()
    root.title('CHIRP RR Scraper')

    # Help menu with 'Find My Location' dialog

    import webbrowser

    menubar = tk.Menu(root)
    helpmenu = tk.Menu(menubar, tearoff=0)

    def open_donations():
        # Open the local index.html in the default web browser
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'media', 'index.html'))
        webbrowser.open(f'file://{html_path}')

    helpmenu.add_command(label='Contact/Donations', command=open_donations)
    menubar.add_cascade(label='Help', menu=helpmenu)
    root.config(menu=menubar)

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
    band_listbox.grid(row=start_row+1, column=1, rowspan=len(BAND_RANGES), sticky='n')

    def toggle_band(band):
        if band_vars[band].get():
            band_listbox.insert(tk.END, band)
        else:
            # remove all occurrences
            for i in range(band_listbox.size()-1, -1, -1):
                if band_listbox.get(i) == band:
                    band_listbox.delete(i)

    for j, band in enumerate(BAND_RANGES.keys()):
        v = tk.IntVar(value=1 if band == 'Simplex' else 0)
        band_vars[band] = v
        cb = tk.Checkbutton(root, text=band, variable=v, command=lambda b=band: toggle_band(b))
        cb.grid(row=start_row+1+j, column=0, sticky='w')
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

    tk.Button(root, text='Up', command=move_up).grid(row=start_row+1+len(BAND_RANGES), column=1, sticky='w')
    tk.Button(root, text='Down', command=move_down).grid(row=start_row+1+len(BAND_RANGES), column=1, sticky='e')

    # Export button
    def on_export():
        pages = {}
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
            for tup in scrape_rr(u):
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

        # If NOAA band selected, ensure NOAA weather frequencies are included
        if 'NOAA' in sel_bands:
            for n, f in NOAA_FREQS:
                rows.append({'Name': n, 'Frequency': f, 'Duplex': '', 'Tone': '', 'Comment': 'Weather', 'Band': 'NOAA'})

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
                val = m.group(1)
                return ('Tone', val, val)
            return (t, '', '')

        df_rows = []
        for r in rows:
            name = r.get('Name','')
            freq = r.get('Frequency','')
            band = r.get('Band','')
            # Repeaters are duplex by design
            duplex = '+' if band == 'Repeaters' or (isinstance(freq, (int,float)) and freq >= 147) else '-' if isinstance(freq, (int,float)) and freq < 147 else ''
            offset = compute_offset_local(freq) if duplex == '+' else ''
            tone_label, rTone, cTone = parse_tone_local(r.get('Tone',''))
            dtcs = '023' if rTone else ''
            dtcs_pol = 'NN' if rTone else ''
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
        outdf.to_csv(output_path)
        messagebox.showinfo('Done', f'Wrote {len(outdf)} rows to {output_path}')

    tk.Button(root, text='Export CSV', command=on_export, bg='#4CAF50', fg='white').grid(row=6, column=1, columnspan=2, pady=8)

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
    if _TK_AVAILABLE and os.environ.get('DISPLAY'):
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
            val = m.group(1)
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
