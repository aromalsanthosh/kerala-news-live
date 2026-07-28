#!/usr/bin/env python3
"""Refresh videoId values in channels.js using the YouTube Data API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


API_BASE = "https://www.googleapis.com/youtube/v3"
FILE_PREFIX = (
    "// Data-only channel configuration. videoId values are maintained by\n"
    "// scripts/update-live-streams.py.\n"
    "const CHANNELS = [\n"
)
FILE_SUFFIX = "\n];\n"


def api_get(resource: str, params: dict[str, str], api_key: str) -> dict:
    query = urllib.parse.urlencode({**params, "key": api_key})
    request = urllib.request.Request(
        f"{API_BASE}/{resource}?{query}",
        headers={"Accept": "application/json", "User-Agent": "kerala-news-live-updater/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        try:
            details = json.load(error)
            message = details["error"]["message"]
        except (json.JSONDecodeError, KeyError):
            message = error.reason
        raise RuntimeError(f"YouTube API request failed ({error.code}): {message}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"YouTube API request failed: {error.reason}") from error


def load_channels(path: Path) -> list[dict]:
    content = path.read_text(encoding="utf-8")
    if not content.startswith(FILE_PREFIX) or not content.endswith(FILE_SUFFIX):
        raise ValueError(f"{path} is not in the expected generated format")
    json_array = "[" + content[len(FILE_PREFIX) : -len(FILE_SUFFIX)] + "]"
    channels = json.loads(json_array)

    required = {"name", "Handle", "channelId", "videoId"}
    for index, channel in enumerate(channels, start=1):
        missing = required - channel.keys()
        if missing:
            raise ValueError(f"Channel {index} is missing: {', '.join(sorted(missing))}")
        if not channel["channelId"].startswith("UC"):
            raise ValueError(f"Invalid channelId for {channel['name']}")
    return channels


def find_live_candidates(channel_id: str, api_key: str) -> list[str]:
    result = api_get(
        "search",
        {
            "part": "id",
            "channelId": channel_id,
            "eventType": "live",
            "type": "video",
            "maxResults": "3",
        },
        api_key,
    )
    return [
        item["id"]["videoId"]
        for item in result.get("items", [])
        if item.get("id", {}).get("videoId")
    ]


def get_embeddable_video_ids(video_ids: list[str], api_key: str) -> set[str]:
    embeddable: set[str] = set()
    for start in range(0, len(video_ids), 50):
        batch = video_ids[start : start + 50]
        result = api_get(
            "videos",
            {"part": "status,snippet", "id": ",".join(batch)},
            api_key,
        )
        for item in result.get("items", []):
            status = item.get("status", {})
            snippet = item.get("snippet", {})
            if (
                status.get("embeddable")
                and status.get("privacyStatus") == "public"
                and snippet.get("liveBroadcastContent") == "live"
            ):
                embeddable.add(item["id"])
    return embeddable


def render_channels(channels: list[dict]) -> str:
    rows = [
        "  " + json.dumps(channel, ensure_ascii=False, separators=(", ", ": "))
        for channel in channels
    ]
    return FILE_PREFIX + ",\n".join(rows) + FILE_SUFFIX


def write_atomically(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="\n",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    try:
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_channels = Path(__file__).resolve().parents[1] / "channels.js"
    parser.add_argument("--channels", type=Path, default=default_channels)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("YOUTUBE_API_KEY is not set", file=sys.stderr)
        return 2

    try:
        channels = load_channels(args.channels)
        candidates_by_channel: list[list[str]] = []
        for channel in channels:
            candidates = find_live_candidates(channel["channelId"], api_key)
            candidates_by_channel.append(candidates)

        all_candidates = list(
            dict.fromkeys(video_id for candidates in candidates_by_channel for video_id in candidates)
        )
        embeddable = get_embeddable_video_ids(all_candidates, api_key)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Update aborted: {error}", file=sys.stderr)
        return 1

    changed = 0
    for channel, candidates in zip(channels, candidates_by_channel):
        previous = channel["videoId"]
        current = next((video_id for video_id in candidates if video_id in embeddable), None)
        channel["videoId"] = current
        if current != previous:
            changed += 1
            print(f"UPDATED  {channel['name']}: {previous or '-'} -> {current or 'offline'}")
        elif current:
            print(f"UNCHANGED {channel['name']}: {current}")
        else:
            print(f"OFFLINE  {channel['name']}")

    if args.dry_run:
        print(f"Dry run complete; {changed} change(s) found")
    else:
        try:
            write_atomically(args.channels, render_channels(channels))
        except OSError as error:
            print(f"Could not write {args.channels}: {error}", file=sys.stderr)
            return 1
        print(f"Updated {args.channels} atomically; {changed} change(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
