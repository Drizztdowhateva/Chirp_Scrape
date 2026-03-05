#!/usr/bin/env python3
# media_scraper.py
#
# Scrapes media files (images, audio, video) from a given URL and saves them
# to a local output directory.  Works as both a standalone CLI tool and an
# importable module.
#
# Usage:
#   python3 media_scraper.py <url> [--output <dir>] [--types <ext,...>]
#
# Examples:
#   python3 media_scraper.py https://example.com/gallery
#   python3 media_scraper.py https://example.com --output ~/Downloads/media --types jpg,png,mp3

import os
import re
import sys
import argparse
import mimetypes
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Default configuration
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media")

# Media file extensions to look for (case-insensitive)
DEFAULT_MEDIA_TYPES = {
    # Images
    "jpg", "jpeg", "png", "gif", "webp", "bmp", "svg",
    # Audio
    "mp3", "wav", "ogg", "flac", "aac", "m4a",
    # Video
    "mp4", "webm", "mkv", "avi", "mov",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/115.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 15  # seconds


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _ext_from_url(url):
    """Return the lowercase file extension of a URL path, or empty string."""
    path = urlparse(url).path
    _, ext = os.path.splitext(path)
    return ext.lower().lstrip(".")


def _is_media_url(url, allowed_types):
    """Return True if the URL looks like a media file of an allowed type."""
    return _ext_from_url(url) in allowed_types


def _safe_filename(url, index, content_type=None):
    """Derive a safe local filename from a URL."""
    path = urlparse(url).path
    basename = os.path.basename(path) or f"media_{index}"
    # Ensure we have an extension
    _, ext = os.path.splitext(basename)
    if not ext and content_type:
        guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if guessed:
            basename = basename + guessed
    # Replace characters that are unsafe in filenames
    basename = re.sub(r'[^\w.\-]', '_', basename)
    return basename


def collect_media_urls(page_url, allowed_types=None, session=None):
    """
    Fetch *page_url* and return a list of absolute media URLs found in the
    page's ``<img>``, ``<audio>``, ``<video>``, ``<source>``, and ``<a>``
    elements.

    Parameters
    ----------
    page_url : str
        The URL of the web page to scan.
    allowed_types : set of str, optional
        Lowercase file extensions to accept (without leading dot).
        Defaults to :data:`DEFAULT_MEDIA_TYPES`.
    session : requests.Session, optional
        Re-use an existing session (useful for authenticated scraping).

    Returns
    -------
    list of str
        Deduplicated list of absolute media URLs.
    """
    if allowed_types is None:
        allowed_types = DEFAULT_MEDIA_TYPES

    req = session or requests

    try:
        resp = req.get(page_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to fetch {page_url}: {exc}") from exc

    soup = BeautifulSoup(resp.text, "html.parser")
    seen = set()
    urls = []

    # Tags and their attribute(s) that may contain media URLs
    tag_attrs = [
        ("img", ["src", "data-src"]),
        ("audio", ["src"]),
        ("video", ["src", "poster"]),
        ("source", ["src"]),
        ("a", ["href"]),
    ]

    for tag_name, attrs in tag_attrs:
        for tag in soup.find_all(tag_name):
            for attr in attrs:
                raw = tag.get(attr, "").strip()
                if not raw:
                    continue
                abs_url = urljoin(page_url, raw)
                if abs_url in seen:
                    continue
                if _is_media_url(abs_url, allowed_types):
                    seen.add(abs_url)
                    urls.append(abs_url)

    return urls


def download_media(url, output_dir, index=0, session=None):
    """
    Download a single media file from *url* into *output_dir*.

    Parameters
    ----------
    url : str
        Direct URL of the media file to download.
    output_dir : str
        Local directory to save the file in (created if it does not exist).
    index : int
        Sequential number used when deriving a filename from the URL.
    session : requests.Session, optional
        Re-use an existing session.

    Returns
    -------
    str
        Absolute path to the saved file, or ``None`` if the download failed.
    """
    os.makedirs(output_dir, exist_ok=True)
    req = session or requests

    try:
        resp = req.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, stream=True)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"  [SKIP] {url} — {exc}")
        return None

    content_type = resp.headers.get("Content-Type", "")
    filename = _safe_filename(url, index, content_type)
    base, ext = os.path.splitext(filename)
    dest = os.path.join(output_dir, filename)

    # Avoid clobbering existing files by incrementing a counter until unique
    counter = 1
    while os.path.exists(dest):
        dest = os.path.join(output_dir, f"{base}_{counter}{ext}")
        counter += 1

    try:
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=8192):
                fh.write(chunk)
    except OSError as exc:
        print(f"  [ERROR] Could not write {dest}: {exc}")
        return None

    return dest


def scrape_media(page_url, output_dir=None, allowed_types=None):
    """
    High-level entry point: scan *page_url* for media files and download them
    all into *output_dir*.

    Parameters
    ----------
    page_url : str
        URL of the page to scrape.
    output_dir : str, optional
        Local directory to save files in.  Defaults to ``media/`` inside the
        project root.
    allowed_types : set of str, optional
        Lowercase extensions to consider (default: :data:`DEFAULT_MEDIA_TYPES`).

    Returns
    -------
    list of str
        Paths of all successfully downloaded files.
    """
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR
    if allowed_types is None:
        allowed_types = DEFAULT_MEDIA_TYPES

    print(f"Scanning {page_url} for media …")
    media_urls = collect_media_urls(page_url, allowed_types)

    if not media_urls:
        print("No media files found on that page.")
        return []

    print(f"Found {len(media_urls)} media URL(s).  Downloading to {output_dir} …")
    saved = []
    for i, url in enumerate(media_urls, start=1):
        print(f"  [{i}/{len(media_urls)}] {url}")
        dest = download_media(url, output_dir, index=i)
        if dest:
            print(f"    → saved: {dest}")
            saved.append(dest)

    print(f"\nDone. {len(saved)}/{len(media_urls)} file(s) saved to {output_dir}.")
    return saved


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_parser():
    parser = argparse.ArgumentParser(
        prog="media_scraper",
        description=(
            "Scrape media files (images, audio, video) from a web page "
            "and save them to a local directory."
        ),
    )
    parser.add_argument(
        "url",
        help="URL of the page to scrape for media files.",
    )
    parser.add_argument(
        "--output", "-o",
        default=DEFAULT_OUTPUT_DIR,
        metavar="DIR",
        help=(
            "Directory to save downloaded files "
            f"(default: {DEFAULT_OUTPUT_DIR})."
        ),
    )
    parser.add_argument(
        "--types", "-t",
        default=None,
        metavar="EXT,...",
        help=(
            "Comma-separated list of file extensions to download "
            "(e.g. jpg,png,mp3).  Defaults to a broad set of common "
            "image/audio/video types."
        ),
    )
    return parser


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)

    allowed_types = DEFAULT_MEDIA_TYPES
    if args.types:
        allowed_types = {t.strip().lower().lstrip(".") for t in args.types.split(",")}

    try:
        scrape_media(args.url, output_dir=args.output, allowed_types=allowed_types)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
