#!/usr/bin/env python3
"""Scrape RadioReference CTID page, follow subcategory links to repeater detail pages,
and extract duplex/offset/tone fields for 2m and 70cm repeaters.
Writes results to media/test_60626_repeaters_rr_details.csv
"""
import os
import re
import csv
import requests
from bs4 import BeautifulSoup

CTID = 606
BASE = 'https://www.radioreference.com'
URL = f'{BASE}/db/browse/ctid/{CTID}/ham'
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'media', 'test_60626_repeaters_rr_details.csv')
HEAD = ['Location','Name','Frequency','Duplex','Offset','Tone','rToneFreq','cToneFreq','DtcsCode','DtcsPolarity','Mode','TStep','Skip','Comment']

def get_soup(url):
    headers = {'User-Agent': 'chirp-rr-details/1.0'}
    r = requests.get(url, headers=headers, timeout=12)
    r.raise_for_status()
    return BeautifulSoup(r.text, 'html.parser')

def norm_href(href):
    if href.startswith('/'):
        return BASE + href
    return href

def is_subcat(href):
    return '/db/subcat/' in href

def is_candidate_detail(href):
    # candidate detail pages: /db/entry/ or other /db/ links that are not browse/subcat/query
    if '/db/' not in href:
        return False
    bad = ['/db/browse', '/db/subcat', '/db/query', '/db/stid', '/db/ctid']
    for b in bad:
        if b in href:
            return False
    return True

def extract_from_detail(soup, url):
    text = soup.get_text(' ', strip=True)
    # find frequencies
    freqs = re.findall(r"(\d+\.\d+)", text)
    freqset = []
    for f in freqs:
        try:
            fv = float(f)
        except Exception:
            continue
        if 144.0 <= fv <= 148.0 or 420.0 <= fv <= 450.0:
            freqset.append("{:.6f}".format(fv).rstrip('0').rstrip('.'))

    if not freqset:
        return []

    # name heuristic
    name = ''
    h2 = soup.find('h2')
    if h2 and h2.text.strip():
        name = h2.text.strip()
    elif soup.title and soup.title.text:
        name = soup.title.text.strip()
    else:
        name = url

    # duplex: look for Plus/Minus or +/ - near frequency
    duplex = ''
    if re.search(r'\bPlus\b|\bMinus\b|\+|\bTx\b', text, re.IGNORECASE):
        if '+' in text:
            duplex = '+'
        elif '-' in text:
            duplex = '-'
        else:
            # fallback based on word
            if re.search(r'\bPlus\b', text, re.IGNORECASE):
                duplex = '+'
            elif re.search(r'\bMinus\b', text, re.IGNORECASE):
                duplex = '-'

    # tone detection: any decimal number not in frequency ranges
    tone = ''
    tones = []
    for m in re.findall(r"(\d+\.\d+)", text):
        try:
            mv = float(m)
        except Exception:
            continue
        if not (144.0 <= mv <= 148.0 or 420.0 <= mv <= 450.0):
            # likely a tone (e.g., 107.2, 88.5)
            tones.append(str(m))
    if tones:
        tone = tones[0]

    # DCS/DPL 3-digit codes
    dtcs = ''
    dcs = re.search(r"\b(\d{3})\b", text)
    if dcs:
        maybe = dcs.group(1)
        # ensure it's not part of a frequency (e.g., 447.975 has 447 but not 3-digit alone)
        dtcs = maybe

    # mode detection
    mode = 'FM'
    for mkey in ('DMR','D-STAR','DSTAR','P25','P-25','YSF','C4FM','FM','AM'):
        if mkey.upper() in text.upper():
            mode = mkey.replace('-', '')
            break

    rows = []
    for f in freqset:
        fv = float(f)
        # default offset
        offset = ''
        if 144.0 <= fv < 148.0:
            offset = '0.600'
            if not duplex:
                duplex = '+' if '+' in text else ''
        elif 420.0 <= fv <= 450.0:
            offset = '5.000'
            if not duplex:
                duplex = '+' if '+' in text else ''

        rows.append({
            'Location': None,
            'Name': name,
            'Frequency': f,
            'Duplex': duplex,
            'Offset': offset,
            'Tone': tone,
            'rToneFreq': tone,
            'cToneFreq': tone,
            'DtcsCode': dtcs,
            'DtcsPolarity': '',
            'Mode': mode,
            'TStep': 5,
            'Skip': '',
            'Comment': url
        })

    return rows


def extract_from_list_page(soup, url):
    # parse table rows on listing/subcategory pages
    rows = []
    for tr in soup.find_all('tr'):
        tds = [td.get_text(' ', strip=True) for td in tr.find_all('td')]
        if len(tds) < 2:
            continue
        freq_cell = tds[1]
        m = re.search(r"(\d+\.\d+)", freq_cell)
        if not m:
            continue
        freq = m.group(1)
        name = ''
        if len(tds) >= 6 and tds[5]:
            name = tds[5]
        elif len(tds) >= 4 and tds[3]:
            name = tds[3]
        elif len(tds) >= 3 and tds[2]:
            name = tds[2]
        else:
            name = tds[0]

        # duplex hint
        duplex = ''
        if '+' in freq_cell:
            duplex = '+'
        elif '-' in freq_cell:
            duplex = '-'

        # tone detection: search tds blob
        text_blob = ' '.join(tds)
        tone = ''
        cc_match = re.search(r"(?:CC|CTCSS)[:#\s]*([0-9]+\.?[0-9]*)", text_blob, re.IGNORECASE)
        if cc_match:
            tone = cc_match.group(1)
        else:
            nums = re.findall(r"(\d+\.\d+)", text_blob)
            if len(nums) >= 2:
                # second numeric token likely tone
                tone = nums[1]

        dtcs = ''
        dcs_match = re.search(r"(?:DCS|DPL|Dtcs|D-PL)[:#\s]*([0-9]{3})", text_blob, re.IGNORECASE)
        if dcs_match:
            dtcs = dcs_match.group(1)
        else:
            three = re.findall(r"\b(\d{3})\b", text_blob)
            for t in three:
                if t not in freq:
                    dtcs = t
                    break

        # mode
        mode = 'FM'
        for mkey in ('DMR','D-STAR','DSTAR','P25','P-25','YSF','FM','AM'):
            if mkey.upper() in text_blob.upper():
                mode = mkey.replace('-', '')
                break

        # offset default by band
        try:
            fv = float(freq)
            if 144.0 <= fv < 148.0:
                offset = '0.600'
            elif 420.0 <= fv <= 450.0:
                offset = '5.000'
            else:
                offset = ''
        except Exception:
            offset = ''

        rows.append({
            'Location': None,
            'Name': name,
            'Frequency': freq,
            'Duplex': duplex,
            'Offset': offset,
            'Tone': tone,
            'rToneFreq': tone,
            'cToneFreq': tone,
            'DtcsCode': dtcs,
            'DtcsPolarity': '',
            'Mode': mode,
            'TStep': 5,
            'Skip': '',
            'Comment': url
        })

    return rows

def scrape():
    top = get_soup(URL)
    # collect subcategory links first
    subcats = set()
    for a in top.find_all('a', href=True):
        href = a['href']
        if is_subcat(href):
            subcats.add(norm_href(href))

    detail_links = set()
    # from CTID page also collect any direct candidate details
    for a in top.find_all('a', href=True):
        href = a['href']
        if is_candidate_detail(href):
            detail_links.add(norm_href(href))
    # start building rows by parsing the CTID listing itself
    rows = []
    # parse listing/table on top page
    try:
        rows += extract_from_list_page(top, URL)
    except Exception:
        pass

    # follow each subcategory to parse listing pages and collect detail links
    for s in list(subcats):
        try:
            soup = get_soup(s)
        except Exception:
            continue
        try:
            rows += extract_from_list_page(soup, s)
        except Exception:
            pass
        for a in soup.find_all('a', href=True):
            href = a['href']
            if is_candidate_detail(href):
                detail_links.add(norm_href(href))

    seen = set()
    for link in detail_links:
        try:
            dsoup = get_soup(link)
        except Exception:
            continue
        extracted = extract_from_detail(dsoup, link)
        for r in extracted:
            key = (r['Name'], r['Frequency'])
            if key in seen:
                continue
            seen.add(key)
            r['Location'] = len(rows) + 1
            rows.append(r)

    # dedupe any rows gathered from list pages
    final = []
    for r in rows:
        key = (r['Name'], r['Frequency'])
        if key in seen:
            # already included from detail_links pass
            continue
        seen.add(key)
        r['Location'] = len(final) + 1
        final.append(r)

    rows = final

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=HEAD)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print('Wrote', len(rows), 'rows to', OUT)

if __name__ == '__main__':
    scrape()
