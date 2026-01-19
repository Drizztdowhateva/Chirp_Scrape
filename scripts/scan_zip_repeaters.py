#!/usr/bin/env python3
import os
import sys
import csv
import time
import requests
from urllib.parse import urlencode

# ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chirp_scraper import scrape_rr, get_defaults_for_freq

RADIOREF_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'radioref.csv')

# Accept ZIP code as first positional argument (default 60626)
import argparse
parser = argparse.ArgumentParser(description='Scan repeaters for a ZIP code (uses RadioReference).')
parser.add_argument('zip', nargs='?', default='60626', help='ZIP code to scan (default: 60626)')
args = parser.parse_args()
ZIP = args.zip
OUT_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'media', f'test_{ZIP}_repeaters.csv')

HEAD = ['Location','Name','Frequency','Duplex','Offset','Tone','rToneFreq','cToneFreq','DtcsCode','DtcsPolarity','Mode','TStep','Skip','Comment']


def geocode_zip(zipcode):
    q = {'postalcode': zipcode, 'country': 'US', 'format': 'json', 'limit': 1}
    url = 'https://nominatim.openstreetmap.org/search?' + urlencode(q)
    r = requests.get(url, headers={'User-Agent': 'chirp-zip-scan/1.0'}, timeout=10)
    r.raise_for_status()
    data = r.json()
    if not data:
        return None
    return data[0]


def zip_to_county_state(zipcode):
    # Use zippopotam.us to get lat/lon, then reverse geocode to obtain county and state
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
        nom = requests.get(f'https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}', headers={'User-Agent':'chirp-zip-scan/1.0'}, timeout=8)
        nom.raise_for_status()
        nj = nom.json()
        addr = nj.get('address', {})
        county = addr.get('county')
        return county, state
    except Exception:
        return None, None


def find_ctid_for_county(county, state):
    # radioref.csv has lines: id,url,location_title
    key = f"{county}, {state}".lower()
    with open(RADIOREF_CSV, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader, None)
        for rid, url, title in reader:
            if not title:
                continue
            t = title
            # normalize like 'Cook County, Illinois (IL) Amateur Radio' -> 'Cook County, Illinois'
            if ' - ' in t:
                t = t.split(' - ',1)[0]
            t = t.split(' Amateur Radio')[0]
            t = t.split(' (')[0]
            if t.strip().lower() == key:
                return int(rid), url
    return None, None


def main():
    # Convert ZIP -> county,state -> CTID using radioref.csv
    if ZIP.isdigit() and len(ZIP) == 5:
        county, state = zip_to_county_state(ZIP)
        if not county or not state:
            print('ERROR: could not determine county/state for zip', ZIP)
            sys.exit(1)
        ctid, ctid_url = find_ctid_for_county(county, state)
        if not ctid:
            print(f'ERROR: no CTID found in radioref.csv for {county}, {state} (zip {ZIP})')
            sys.exit(1)
        url = f'https://www.radioreference.com/db/browse/ctid/{ctid}/ham'
        print(f'Resolved zip {ZIP} -> {county}, {state} -> CTID {ctid}')
        print('Scraping', url)
    else:
        url = ZIP
    rows = []
    try:
        entries = scrape_rr(url)
    except Exception as e:
        print('Scrape failed:', e)
        entries = []

    # entries -> tuples (name, freq, tone, duplex, offset, rTone, cTone, dtcs, dtcs_pol, mode)
    for i, e in enumerate(entries, start=1):
        if not e:
            continue
        name = e[0] if len(e) > 0 else ''
        freq = e[1] if len(e) > 1 else ''
        tone = e[2] if len(e) > 2 else ''
        duplex = e[3] if len(e) > 3 else ''
        offset = e[4] if len(e) > 4 else ''
        rTone = e[5] if len(e) > 5 else ''
        cTone = e[6] if len(e) > 6 else ''
        dtcs = e[7] if len(e) > 7 else ''
        dtcsp = e[8] if len(e) > 8 else ''
        mode = e[9] if len(e) > 9 else 'FM'
        # apply defaults from csv_files if missing
        try:
            fval = float(freq)
        except Exception:
            fval = None
        if fval is not None:
            defaults = get_defaults_for_freq(fval)
            if defaults:
                if not tone:
                    tone = defaults.get('Tone','') or ''
                if not rTone:
                    rTone = defaults.get('rToneFreq','') or ''
                if not cTone:
                    cTone = defaults.get('cToneFreq','') or ''
                if not dtcs:
                    dtcs = defaults.get('DtcsCode','') or ''
                if not dtcsp:
                    dtcsp = defaults.get('DtcsPolarity','') or ''
        rows.append({
            'Location': i,
            'Name': name,
            'Frequency': freq,
            'Duplex': duplex,
            'Offset': offset,
            'Tone': tone,
            'rToneFreq': rTone,
            'cToneFreq': cTone,
            'DtcsCode': dtcs,
            'DtcsPolarity': dtcsp,
            'Mode': mode,
            'TStep': 5,
            'Skip': '',
            'Comment': ''
        })

    # Write CSV like your sample file (Location + fields)
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=HEAD)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print('Wrote', len(rows), 'rows to', OUT_CSV)

if __name__ == '__main__':
    main()
