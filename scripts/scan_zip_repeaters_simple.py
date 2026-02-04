#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import csv
import os
import re
import argparse
import sys

# Accept ZIP (or CTID) as an optional first argument. Default to ZIP 60626 -> CTID 606 behavior.
parser = argparse.ArgumentParser(description='Simple RadioReference CTID scraper. Pass a ZIP code or leave empty for default 60626.')
parser.add_argument('zip', nargs='?', default='60626', help='ZIP code or identifier (default: 60626)')
args = parser.parse_args()

RADIOREF_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'radioref.csv')
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'media', f'test_{args.zip}_repeaters.csv')
HEAD = ['Location','Name','Frequency','Duplex','Offset','Tone','rToneFreq','cToneFreq','DtcsCode','DtcsPolarity','Mode','TStep','Skip','Comment']

# Resolve ZIP to a RadioReference page using chirp_scraper helper when possible
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def zip_to_county_state(zipcode):
    try:
        zr = requests.get(f'http://api.zippopotam.us/us/{zipcode}', timeout=8)
        zr.raise_for_status()
        pj = zr.json()
        places = pj.get('places', [])
        if not places:
            return None, None
        lat = places[0].get('latitude')
        lon = places[0].get('longitude')
        state = places[0].get('state')
        if not lat or not lon:
            return None, None
        nom = requests.get(f'https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}', headers={'User-Agent':'chirp-zip-scan-simple/1.0'}, timeout=8)
        nom.raise_for_status()
        nj = nom.json()
        addr = nj.get('address', {})
        county = addr.get('county')
        return county, state
    except Exception:
        return None, None


def find_ctid_for_county(county, state):
    if not county or not state:
        return None
    key = f"{county}, {state}".lower()
    with open(RADIOREF_CSV, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader, None)
        for rid, url, title in reader:
            if not title:
                continue
            t = title
            if ' - ' in t:
                t = t.split(' - ',1)[0]
            t = t.split(' Amateur Radio')[0]
            t = t.split(' (')[0]
            if t.strip().lower() == key:
                try:
                    return int(rid)
                except Exception:
                    return None
    return None


# Resolve ZIP -> CTID using radioref.csv; do not fall back to ZIP browse pages
if re.match(r'^\d{5}$', args.zip):
    county, state = zip_to_county_state(args.zip)
    if not county or not state:
        print('ERROR: could not determine county/state for zip', args.zip)
        sys.exit(1)
    ctid = find_ctid_for_county(county, state)
    if not ctid:
        print(f'ERROR: no CTID found in radioref.csv for {county}, {state} (zip {args.zip})')
        sys.exit(1)
    URL = f'https://www.radioreference.com/db/browse/ctid/{ctid}/ham'
else:
    try:
        cid = int(args.zip)
        URL = f'https://www.radioreference.com/db/browse/ctid/{cid}/ham'
    except Exception:
        print('ERROR: argument must be a 5-digit ZIP or a numeric CTID')
        sys.exit(1)

print('Fetching', URL)
r = requests.get(URL, headers={'User-Agent':'chirp-zip-scan-simple/1.0'}, timeout=15)
r.raise_for_status()
soup = BeautifulSoup(r.text, 'html.parser')
# find main table of repeaters
table = soup.find('table')
rows = []
if table:
    for i, tr in enumerate(table.find_all('tr'), start=1):
        tds = [td.get_text(separator=' ', strip=True) for td in tr.find_all('td')]
        if len(tds) < 2:
            continue
        # heuristic: frequency often in 2nd cell
        freq = ''
        name = ''
        if len(tds) >= 2:
            freq = tds[1]
        if len(tds) >= 4:
            name = tds[3]
        elif len(tds) >= 3:
            name = tds[2]
        else:
            name = tds[0]
        # clean up frequency to numeric-like
        import re
        m = re.search(r"(\d+\.\d+)", freq)
        if m:
            freq = m.group(1)
        else:
            # skip non-frequency rows
            continue
        rows.append({
            'Location': len(rows)+1,
            'Name': name,
            'Frequency': freq,
            'Duplex': '',
            'Offset': '',
            'Tone': '',
            'rToneFreq': '',
            'cToneFreq': '',
            'DtcsCode': '',
            'DtcsPolarity': '',
            'Mode': 'FM',
            'TStep': 5,
            'Skip': '',
            'Comment': ''
        })
else:
    print('No table found on page; aborting')

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=HEAD)
    w.writeheader()
    for r in rows:
        w.writerow(r)
print('Wrote', len(rows), 'rows to', OUT)
