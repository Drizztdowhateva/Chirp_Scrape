#!/usr/bin/env python3
"""Scrape RepeaterBook search results for a ZIP code and extract 2m/70cm frequencies.
Writes to media/test_60626_repeaters_rb.csv
"""
import os
import re
import csv
import requests
from bs4 import BeautifulSoup

ZIP = '60626'
URL = f'https://www.repeaterbook.com/repeaters/results.php?zip={ZIP}'
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'media', 'test_60626_repeaters_rb.csv')
HEAD = ['Location','Name','Frequency','Duplex','Offset','Tone','rToneFreq','cToneFreq','DtcsCode','DtcsPolarity','Mode','TStep','Skip','Comment']

def extract_freqs(text):
    nums = re.findall(r"(\d+\.\d+)", text)
    freqs = set()
    for n in nums:
        try:
            f = float(n)
        except Exception:
            continue
        if 144.0 <= f <= 148.0 or 420.0 <= f <= 450.0:
            freqs.add("{:.6f}".format(f).rstrip('0').rstrip('.'))
    return sorted(freqs)

def extract_tone(text):
    m = re.search(r"(?:CTCSS|Tone|Tone\s*[:#])\s*([0-9]+\.?[0-9]*)", text, re.IGNORECASE)
    if m:
        return m.group(1)
    return ''

def scrape():
    headers = {'User-Agent': 'chirp-rb-scraper/1.0'}
    r = requests.get(URL, headers=headers, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    rows = []
    seen = set()
    # look for repeater result blocks; heuristic: links with 'repeater' or table rows
    for i, block in enumerate(soup.find_all(['tr','div','li']), start=1):
        text = block.get_text(' ', strip=True)
        freqs = extract_freqs(text)
        if not freqs:
            continue
        tone = extract_tone(text)
        name = ''
        a = block.find('a')
        if a and a.text:
            name = a.text.strip()
        else:
            name = text.split('  ')[0][:60]
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
                'Comment': URL
            })

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=HEAD)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print('Wrote', len(rows), 'rows to', OUT)

if __name__ == '__main__':
    scrape()
