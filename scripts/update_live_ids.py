#!/usr/bin/env python3
"""Refresh the live video IDs in index.html's CHANNELS array.

Two lookup modes:

* YouTube Data API (used when YOUTUBE_API_KEY is set) -- reliable. Lists each
  channel's live broadcasts and checks that the stream is embeddable and not
  age-restricted. Costs ~101 quota units per channel (default quota: 10,000/day).
* Page scraping (fallback) -- reads youtube.com/channel/<id>/live and the
  channel's /streams tab. YouTube often answers datacenter IPs (such as GitHub
  Actions runners) with a "confirm you're not a bot" page, so this mode may
  find only some channels.

A new ID is only written when it passes the embed checks; otherwise the
existing ID is kept, so a failed lookup never makes things worse.

Usage: python3 scripts/update_live_ids.py [path/to/index.html]
"""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

INDEX = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "index.html")
API_KEY = os.environ.get("YOUTUBE_API_KEY", "").strip()

# One line per channel: { id: "...", channel: "UC...", name: "..." ... },
LINE_RE = re.compile(r'(\{\s*id:\s*")([^"]+)(",\s*channel:\s*")(UC[\w-]{22})(",\s*name:\s*"([^"]+)")')
CANONICAL_RE = re.compile(r'<link rel="canonical" href="https://www\.youtube\.com/watch\?v=([\w-]{11})"')
LIVE_FLAG_RE = re.compile(r'"isLiveNow":\s*true|"isLive":\s*true')
VIDEO_ID_RE = re.compile(r'"videoId":\s*"([\w-]{11})"')
VIDEO_DETAILS_RE = re.compile(r'"videoDetails":\s*\{')
# Newer channel-tab markup ("lockupViewModel") stores the video ID as contentId.
LOCKUP_RE = re.compile(r'"lockupViewModel":\s*\{')
CONTENT_ID_RE = re.compile(r'"contentId":\s*"([\w-]{11})"')
LIVE_BADGES = (
    'STYLE_LIVE',
    '"style":"LIVE"',
    '"iconType":"LIVE"',
    "BADGE_STYLE_TYPE_LIVE_NOW",
    "THUMBNAIL_OVERLAY_BADGE_STYLE_LIVE",
    '"overlayStyle":"LIVE"',
)
# Signs in a watch page that the video can't play in an embed for everyone.
UNEMBEDDABLE_MARKERS = (
    '"isFamilySafe":false',
    "confirm your age",
    "AGE_VERIFICATION_REQUIRED",
    "AGE_CHECK_REQUIRED",
    '"playableInEmbed":false',
)
BOT_CHECK_MARKER = "confirm you’re not a bot"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    # Skip the EU cookie-consent interstitial.
    "Cookie": "CONSENT=YES+1; SOCS=CAI",
}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.load(resp)


# --------------------------------------------------------------------------- API


def api_live_ids(channel_id: str, current: str) -> tuple[str | None, str]:
    base = "https://www.googleapis.com/youtube/v3"
    q = urllib.parse.urlencode(
        {"part": "id", "channelId": channel_id, "eventType": "live", "type": "video", "maxResults": 10, "key": API_KEY}
    )
    ids = [it["id"]["videoId"] for it in fetch_json(f"{base}/search?{q}").get("items", [])]
    if not ids:
        return None, "API: no live broadcasts"
    q = urllib.parse.urlencode(
        {"part": "status,contentDetails,snippet", "id": ",".join(ids), "key": API_KEY}
    )
    ok, rejected = [], []
    for v in fetch_json(f"{base}/videos?{q}").get("items", []):
        if v["snippet"].get("liveBroadcastContent") != "live":
            rejected.append(f"{v['id']}(not live)")
        elif not v["status"].get("embeddable", False):
            rejected.append(f"{v['id']}(embedding disabled)")
        elif v.get("contentDetails", {}).get("contentRating", {}).get("ytRating") == "ytAgeRestricted":
            rejected.append(f"{v['id']}(age-restricted)")
        else:
            ok.append(v["id"])
    if not ok:
        return None, "API: no embeddable live stream; rejected " + ", ".join(rejected)
    # Channels sometimes run several streams; don't flip-flop if ours is still fine.
    return (current if current in ok else ok[0]), "API"


# ---------------------------------------------------------------------- scraping


def oembed_ok(video_id: str) -> bool:
    """oEmbed answers 401/403/404 for videos that can't be embedded."""
    url = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(
        f"https://www.youtube.com/watch?v={video_id}", safe=""
    )
    try:
        fetch(url)
        return True
    except urllib.error.HTTPError:
        return False


def scrape_candidates(channel_id: str) -> tuple[list[tuple[str, str]], list[str]]:
    """Return ([(video_id, page_html_or_empty)], notes)."""
    cands, notes = [], []

    html = fetch(f"https://www.youtube.com/channel/{channel_id}/live")
    if BOT_CHECK_MARKER in html or "confirm you're not a bot" in html:
        notes.append("live page: bot check")
    if LIVE_FLAG_RE.search(html):
        m = CANONICAL_RE.search(html)
        if not m:
            d = VIDEO_DETAILS_RE.search(html)
            m = VIDEO_ID_RE.search(html, d.end(), d.end() + 600) if d else None
        if m:
            cands.append((m.group(1), html))
    if not cands:
        notes.append("live page: no live video")

    html = fetch(f"https://www.youtube.com/channel/{channel_id}/streams")
    found = []
    # New layout: one lockupViewModel per video, carrying contentId and badges.
    starts = [m.start() for m in LOCKUP_RE.finditer(html)]
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(html)
        seg = html[start:end]
        m = CONTENT_ID_RE.search(seg)
        if m and any(marker in seg for marker in LIVE_BADGES):
            found.append(m.group(1))
    # Old layout: videoRenderer, keyed by videoId.
    ids = [(m.start(), m.group(1)) for m in VIDEO_ID_RE.finditer(html)]
    for i, (start, vid) in enumerate(ids):
        if i and ids[i - 1][1] == vid:
            continue
        end = next((p for p, v in ids[i + 1:] if v != vid), len(html))
        if any(marker in html[start:end] for marker in LIVE_BADGES):
            found.append(vid)
    for vid in found:
        if vid not in [c for c, _ in cands]:
            cands.append((vid, ""))  # no watch page for this one
    if not found:
        notes.append("streams tab: no LIVE badge")
    return cands, notes


def scrape_live_id(channel_id: str, current: str) -> tuple[str | None, str]:
    cands, notes = scrape_candidates(channel_id)
    ok, rejected = [], []
    for vid, page in cands:
        bad = next((mk for mk in UNEMBEDDABLE_MARKERS if mk in page), None)
        if bad:
            rejected.append(f"{vid}({bad})")
        elif not oembed_ok(vid):
            rejected.append(f"{vid}(oEmbed refused)")
        else:
            ok.append(vid)
    if rejected:
        notes.append("rejected " + ", ".join(rejected))
    if not ok:
        return None, "scrape: " + "; ".join(notes)
    return (current if current in ok else ok[0]), "scrape"


def current_live_id(channel_id: str, current: str) -> tuple[str | None, str]:
    if API_KEY:
        return api_live_ids(channel_id, current)
    return scrape_live_id(channel_id, current)


# -------------------------------------------------------------------------- main


def main() -> int:
    text = INDEX.read_text(encoding="utf-8")
    changes = []
    print(f"Mode: {'YouTube Data API' if API_KEY else 'page scraping (set YOUTUBE_API_KEY for reliable results)'}")

    def replace(m: re.Match) -> str:
        old_id, channel_id, name = m.group(2), m.group(4), m.group(6)
        try:
            new_id, how = current_live_id(channel_id, old_id)
        except Exception as e:  # network error, HTTP error, quota, etc.
            print(f"[warn] {name}: lookup failed ({e}); keeping {old_id}")
            return m.group(0)
        if not new_id:
            print(f"[skip] {name}: keeping {old_id} -- {how}")
            return m.group(0)
        if new_id == old_id:
            print(f"[ok]   {name}: unchanged ({old_id}, via {how})")
            return m.group(0)
        print(f"[new]  {name}: {old_id} -> {new_id} (via {how})")
        changes.append(name)
        return m.group(1) + new_id + m.group(3) + channel_id + m.group(5)

    new_text, count = LINE_RE.subn(replace, text)
    if count == 0:
        print("No CHANNELS entries found in", INDEX)
        return 1
    if changes:
        INDEX.write_text(new_text, encoding="utf-8")
        print(f"Updated {len(changes)} channel(s): {', '.join(changes)}")
    else:
        print("No changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
