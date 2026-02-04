#!/usr/bin/env python3
"""Follow RadioReference repeater links from a CTID page and extract frequencies.
Writes 2m and 70cm entries to media/test_60626_repeaters_rr_full.csv
"""
import os
import re
import csv
import requests
from bs4 import BeautifulSoup

CTID = 606
URL = f'https://www.radioreference.com/db/browse/ctid/{CTID}/ham'
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'media', 'test_60626_repeaters_rr_full.csv')
HEAD = ['Location','Name','Frequency','Duplex','Offset','Tone','rToneFreq','cToneFreq','DtcsCode','DtcsPolarity','Mode','TStep','Skip','Comment']

RR_HEADERS = HEAD

def find_detail_links(soup):
    links = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        # heuristic: repeater detail pages usually include '/db/' and not external
        if '/db/' in href or 'index.php' in href:
            if href.startswith('/'):
                href = 'https://www.radioreference.com' + href
            if href.startswith('http'):
                links.add(href)
    return list(links)

def extract_freqs_from_text(text):
    nums = re.findall(r"(\d+\.\d+)", text)
    freqs = set()
    for n in nums:
        try:
            f = float(n)
        except Exception:
            continue
        # 2m: 144-148, 70cm: 420-450
        if 144.0 <= f <= 148.0 or 420.0 <= f <= 450.0:
            freqs.add("{:.6f}".format(f).rstrip('0').rstrip('.'))
    return sorted(freqs)

def extract_tone(text):
    m = re.search(r"(?:CTCSS|Tone|CC|DPL)[:#\s]*([0-9]+\.?[0-9]*)", text, re.IGNORECASE)
    if m:
        return m.group(1)
    return ''

def scrape():
    headers = {'User-Agent': 'chirp-rr-follow/1.0'}
    r = requests.get(URL, headers=headers, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    links = find_detail_links(soup)

    rows = []
    seen = set()
    for link in links:
        try:
            rr = requests.get(link, headers=headers, timeout=12)
            rr.raise_for_status()
            text = rr.text
            freqs = extract_freqs_from_text(text)
            if not freqs:
                continue
            tone = extract_tone(text)
            # name heuristic: page title or first h1/h2
            psoup = BeautifulSoup(text, 'html.parser')
            name = psoup.title.text.strip() if psoup.title and psoup.title.text else link
            for f in freqs:
                key = (name, f)
                if key in seen:
                    continue
                seen.add(key)
                rows.append({
                    'Location': len(rows)+1,
                    'Name': name,
                    'Frequency': f,
                    'Duplex': '',
                    'Offset': '',
                    'Tone': tone,
                    'rToneFreq': tone,
                    'cToneFreq': tone,
                    'DtcsCode': '',
                    'DtcsPolarity': '',
                    'Mode': 'FM',
                    'TStep': 5,
                    'Skip': '',
                    'Comment': link
                })
        except Exception:
            continue

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=RR_HEADERS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print('Wrote', len(rows), 'rows to', OUT)

if __name__ == '__main__':
    scrape()
