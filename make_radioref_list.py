#!/usr/bin/env python3
"""Crawl RadioReference /db/browse/ctid/<id> pages and emit radioref.csv

Defaults are conservative: iterate IDs from 1..max_id and stop early after
`stop_after_missing` consecutive 404s. Adjust `--max-id` and
`--stop-after-missing` for a fuller crawl.
"""
import argparse
import csv
import time
import requests
import re
from bs4 import BeautifulSoup

USER_AGENT = "chirp-radioref-crawler/1.0 (+https://example.com)"


def extract_title_text(html_text: str) -> str:
    soup = BeautifulSoup(html_text, "html.parser")
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
        # common formatting: 'Cook County, Illinois - RadioReference.com'
        if " - " in title:
            return title.split(" - ", 1)[0].strip()
        return title
    # fallback: find h1/h2
    h2 = soup.find("h2")
    if h2 and h2.text:
        return h2.text.strip()
    return ""


def crawl(start_id: int, max_id: int, stop_after_missing: int, delay: float, out_path: str, append: bool = False):
    headers = {"User-Agent": USER_AGENT}
    out_rows = []
    consecutive_missing = 0
    for i in range(start_id, max_id + 1):
        url = f"https://www.radioreference.com/db/browse/ctid/{i}/ham"
        try:
            r = requests.get(url, headers=headers, timeout=10)
        except Exception as e:
            print(f"{i}: request error: {e}")
            time.sleep(delay)
            continue

        if r.status_code == 200:
            title = extract_title_text(r.text)
            # Determine whether title contains usable county/city,state info.
            def has_county_state(t: str) -> bool:
                if not t:
                    return False
                # normalize common suffixes and parenthetical abbreviations
                tt = re.sub(r'\s*Amateur Radio$', '', t, flags=re.I).strip()
                tt = re.sub(r'\s*\([^)]*\)\s*$', '', tt).strip()
                # need a comma separating name and state
                if ',' not in tt:
                    return False
                # accept a variety of jurisdiction keywords (County, Parish, Borough, City, etc.)
                keywords = ['County', 'Parish', 'Borough', 'City', 'Municipality', 'Census Area', 'District', 'Province']
                if any(k in tt for k in keywords):
                    return True
                # fallback: if it looks like 'Name, StateName' treat as valid
                if re.search(r',\s*[A-Za-z\. ]+$', tt):
                    return True
                return False

            if title and has_county_state(title):
                consecutive_missing = 0
                out_rows.append((i, url, title))
                print(f"{i}: FOUND: {title}")
            else:
                consecutive_missing += 1
                print(f"{i}: 200 but no county/state info: '{title}'")
        else:
            consecutive_missing += 1
            print(f"{i}: {r.status_code}")

        if consecutive_missing >= stop_after_missing:
            print(f"Stopping after {consecutive_missing} consecutive missing pages at id {i}")
            break

        time.sleep(delay)

    # write CSV (append or write)
    mode = "a" if append else "w"
    write_header = True
    if append:
        try:
            with open(out_path, "r", encoding="utf-8") as rf:
                # if file non-empty, skip header
                existing = rf.read().strip()
                if existing:
                    write_header = False
        except FileNotFoundError:
            write_header = True

    with open(out_path, mode, newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["id", "url", "location_title"])
        for row in out_rows:
            w.writerow(row)
    print(f"Wrote {len(out_rows)} rows to {out_path} (append={append})")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--start-id", type=int, default=1, help="Start CTID to try")
    p.add_argument("--max-id", type=int, default=1000, help="Maximum CTID to try")
    p.add_argument("--stop-after-missing", type=int, default=10, help="Stop after this many consecutive non-200 or title-missing responses")
    p.add_argument("--stop-on-missing", action='store_true', help="Stop immediately on the first 200 response that lacks county/state title information")
    p.add_argument("--delay", type=float, default=0.1, help="Delay between requests (seconds)")
    p.add_argument("--output", default="radioref.csv", help="Output CSV path")
    p.add_argument("--append", action='store_true', help='Append to output CSV instead of overwriting')
    args = p.parse_args()
    # If --stop-on-missing is set, treat it as stop_after_missing == 1 behavior
    stop_after = 1 if args.stop_on_missing else args.stop_after_missing
    crawl(args.start_id, args.max_id, stop_after, args.delay, args.output, append=args.append)


if __name__ == '__main__':
    main()
