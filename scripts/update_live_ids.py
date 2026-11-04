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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    # Skip the EU cookie-consent interstitial.
    "Cookie": "CONSENT=YES+1; SOCS=CAI",
}


def current_live_id(channel_id: str) -> str | None:
    url = f"https://www.youtube.com/channel/{channel_id}/live"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", "replace")
    m = CANONICAL_RE.search(html)
    if not m or not LIVE_FLAG_RE.search(html):
        return None
    return m.group(1)


def main() -> int:
    text = INDEX.read_text(encoding="utf-8")
    changes = []

    def replace(m: re.Match) -> str:
        old_id, channel_id, name = m.group(2), m.group(4), m.group(6)
        try:
            new_id = current_live_id(channel_id)
        except Exception as e:  # network error, HTTP error, etc.
            print(f"[warn] {name}: lookup failed ({e}); keeping {old_id}")
            return m.group(0)
        if not new_id:
            print(f"[skip] {name}: not live right now; keeping {old_id}")
            return m.group(0)
        if new_id == old_id:
            print(f"[ok]   {name}: unchanged ({old_id})")
            return m.group(0)
        print(f"[new]  {name}: {old_id} -> {new_id}")
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
