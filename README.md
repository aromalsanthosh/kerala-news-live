# Multiple News Live

A lightweight static website for watching multiple YouTube news livestreams
side by side. The responsive grid keeps every visible stream on screen while
allowing audio to be focused on one channel at a time.

The browser application uses plain HTML, CSS, and JavaScript. There is no build
step or frontend dependency. A separate Python utility can refresh each
channel's current YouTube live video ID through the official YouTube Data API.

## Features

- Display multiple news livestreams in a responsive grid.
- Focus audio on one channel while keeping the remaining streams muted.
- Show or hide individual channels and pause hidden players.
- Show all, hide all, or mute all channels from the floating control panel.
- Display an offline state instead of a broken player when no livestream is
  available.
- Update rotating YouTube live video IDs without editing the application code.
- Operate as an ordinary static website on Netlify, Vercel, GitHub Pages, or
  another static host.

### Keyboard shortcuts

- `1`–`9`: focus audio on the corresponding channel.
- `0` or `M`: mute all channels.
- `Esc`: collapse the audio panel.

## Run locally

Serve the project directory with any static web server:

```bash
python3 -m http.server 8000
```

Then open <http://localhost:8000>.

The included `startServer.sh` runs the same command.

## Channel configuration

Channel metadata is kept in the data-only
[`channels.js`](https://github.com/arun-ks/multiple-news-live/blob/main/channels.js)
file:

```js
const CHANNELS = [
  {
    "name": "Channel Name",
    "Handle": "@ChannelHandle",
    "channelId": "UC...",
    "videoId": null
  }
];
```

- `name` is the label shown in the audio panel.
- `Handle` is the channel's human-readable YouTube handle.
- `channelId` is YouTube's immutable `UC...` channel identifier.
- `videoId` identifies the current public, embeddable live broadcast. Use
  `null` when the channel is offline.

The website embeds `videoId` because YouTube's supported player URL requires a
specific video ID. The updater maintains this value for channels that create a
new video for each broadcast.

### Find a channel ID from a handle

Create a YouTube Data API v3 key in Google Cloud, then call the official
`channels.list` endpoint.

PowerShell example:

```powershell
$apiKey = "YOUR_API_KEY"
$handle = "@AsianetNews"
$result = Invoke-RestMethod "https://www.googleapis.com/youtube/v3/channels?part=id&forHandle=$([uri]::EscapeDataString($handle))&key=$apiKey"
$result.items[0].id
```

The result should begin with `UC`. Do not commit the API key to the repository.

## Update live video IDs

[`scripts/update-live-streams.py`](https://github.com/arun-ks/multiple-news-live/blob/main/scripts/update-live-streams.py)
uses the official YouTube Data API. It requires Python 3 and has no third-party
Python dependencies.

macOS/Linux:

```bash
export YOUTUBE_API_KEY="YOUR_API_KEY"
python3 scripts/update-live-streams.py
```

PowerShell:

```powershell
$env:YOUTUBE_API_KEY = "YOUR_API_KEY"
python scripts/update-live-streams.py
```

Preview changes without writing `channels.js`:

```bash
python3 scripts/update-live-streams.py --dry-run
```

For every configured `channelId`, the updater:

1. Searches for active live videos.
2. Confirms that candidates are public and embeddable.
3. Selects the first valid result or records `videoId: null`.
4. Replaces `channels.js` atomically.
5. Logs updated, unchanged, and offline channels.

A complete refresh uses one quota-expensive search request per channel plus
inexpensive validation requests. Running it once or twice a day is appropriate
for the current channel count.

## Project structure

```text
index.html                       Page structure
styles.css                      Responsive layout and controls
channels.js                     Channel metadata and current live video IDs
app.js                          Grid, YouTube players, visibility, and audio
scripts/update-live-streams.py  YouTube Data API updater
startServer.sh                  Optional local static server command
```

## Changes from the upstream project

This repository was derived from
[`aromalsanthosh/kerala-news-live`](https://github.com/aromalsanthosh/kerala-news-live).
The original project provided the responsive multi-stream grid, audio-focus
controls, channel visibility controls, and keyboard interactions.

The implementation was extended on July 28, 2026 with the following functional
changes:

- Expanded and changed the configured news-channel lineup.
- Replaced unreliable channel-live embed URLs with supported video-ID embeds.
- Added immutable YouTube channel IDs and human-readable handles to the channel
  configuration.
- Added an official YouTube Data API updater for rotating live video IDs.
- Added validation for public, embeddable live broadcasts.
- Added explicit offline tiles and disabled audio selection for offline
  channels.
- Split the original single HTML file into `index.html`, `styles.css`,
  `channels.js`, and `app.js`.
- Made `channels.js` a data-only generated file that can be refreshed
  independently and safely by a scheduled job.
- Added the player `origin` parameter for more reliable YouTube IFrame API
  identification.

Thanks to [Aromal Santhosh](https://github.com/aromalsanthosh) for the original
project and interface foundation.

## Notes

- YouTube availability and embedding permissions remain under each channel
  owner's control.
- Browser autoplay policies require streams to start muted.
- YouTube may expose more than one live video for a channel; the updater selects
  the first public and embeddable result returned by the API.
