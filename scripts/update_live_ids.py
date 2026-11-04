#!/usr/bin/env python3
"""Refresh the live video IDs in index.html's CHANNELS array.

For each channel, fetch https://www.youtube.com/channel/<id>/live. When the
channel is live, YouTube serves that stream's watch page, whose canonical URL
contains the current video ID. If a channel isn't live (or the lookup fails),
its existing ID is left untouched.

Usage: python3 scripts/update_live_ids.py [path/to/index.html]
"""
import re
import sys
import urllib.request
from pathlib import Path

INDEX = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "index.html")

# One line per channel: { id: "...", channel: "UC...", name: "..." ... },
LINE_RE = re.compile(r'(\{\s*id:\s*")([^"]+)(",\s*channel:\s*")(UC[\w-]{22})(",\s*name:\s*"([^"]+)")')
CANONICAL_RE = re.compile(r'<link rel="canonical" href="https://www\.youtube\.com/watch\?v=([\w-]{11})"')
LIVE_FLAG_RE = re.compile(r'"isLiveNow":\s*true|"isLive":\s*true')
VIDEO_ID_RE = re.compile(r'"videoId":"([\w-]{11})"')
LIVE_BADGES = ('"style":"LIVE"', '"iconType":"LIVE"', 'BADGE_STYLE_TYPE_LIVE_NOW')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    # Skip the EU cookie-consent interstitial.
    "Cookie": "CONSENT=YES+1; SOCS=CAI",
}


def fetch(url: str) -> tuple[str, str]:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.geturl(), resp.read().decode("utf-8", "replace")


def describe(final_url: str, html: str) -> str:
    """Short reason string for logs when no live ID was found."""
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    canon = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return (f"url={final_url} canonical={canon.group(1) if canon else None} "
            f"title={title.group(1).strip()[:60] if title else None!r} len={len(html)}")


def from_live_page(channel_id: str) -> tuple[str | None, str]:
    final_url, html = fetch(f"https://www.youtube.com/channel/{channel_id}/live")
    m = CANONICAL_RE.search(html)
    if m and LIVE_FLAG_RE.search(html):
        return m.group(1), "live page"
    return None, describe(final_url, html)


def from_streams_tab(channel_id: str) -> tuple[str | None, str]:
    """Fallback: first video on the channel's Live tab that carries a LIVE badge."""
    final_url, html = fetch(f"https://www.youtube.com/channel/{channel_id}/streams")
    ids = [(m.start(), m.group(1)) for m in VIDEO_ID_RE.finditer(html)]
    # Split the page into one segment per video (a video's ID repeats inside its
    # own renderer, so a segment runs until a *different* ID appears).
    for i, (start, vid) in enumerate(ids):
        if i and ids[i - 1][1] == vid:
            continue
        end = next((p for p, v in ids[i + 1:] if v != vid), len(html))
        if any(marker in html[start:end] for marker in LIVE_BADGES):
            return vid, "streams tab"
    return None, describe(final_url, html)


def current_live_id(channel_id: str) -> tuple[str | None, str]:
    vid, why = from_live_page(channel_id)
    if vid:
        return vid, why
    vid2, why2 = from_streams_tab(channel_id)
    if vid2:
        return vid2, why2
    return None, f"live page: {why} | streams: {why2}"


def main() -> int:
    text = INDEX.read_text(encoding="utf-8")
    changes = []

    def replace(m: re.Match) -> str:
        old_id, channel_id, name = m.group(2), m.group(4), m.group(6)
        try:
            new_id, how = current_live_id(channel_id)
        except Exception as e:  # network error, HTTP error, etc.
            print(f"[warn] {name}: lookup failed ({e}); keeping {old_id}")
            return m.group(0)
        if not new_id:
            print(f"[skip] {name}: no live stream found; keeping {old_id}\n       {how}")
            return m.group(0)
        if new_id == old_id:
            print(f"[ok]   {name}: unchanged ({old_id}, via {how})")
            return m.group(0)
        print(f"[new]  {name}: {old_id} -> {new_id} (via {how})")
        changes.append(f"{name}: {old_id} -> {new_id}")
        return m.group(1) + new_id + m.group(3) + channel_id + m.group(5)

    new_text, count = LINE_RE.subn(replace, text)
    if count == 0:
        print("No CHANNELS entries found in", INDEX)
        return 1
    if changes:
        INDEX.write_text(new_text, encoding="utf-8")
        print(f"Updated {len(changes)} channel(s).")
    else:
        print("No changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
