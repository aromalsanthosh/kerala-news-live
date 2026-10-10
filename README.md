# kerala-news-live

A lightweight single-page app for watching **multiple Malayalam news channel YouTube live streams side-by-side** in one responsive grid. Built with plain HTML/CSS/JS — no build step, no dependencies.

## Why

Malayalam news coverage (especially during elections, breaking news, budgets, etc.) is spread across many channels running simultaneously. Instead of juggling tabs, this page shows them all at once and lets you focus audio on one channel at a time.

## Features

- **Multi-stream grid** — watch 9+ Malayalam news channels (24, Asianet, Reporter, Big TV, Manorama, Mathrubhumi, Janam, Media One, Kairali) concurrently, plus News Malayalam 24x7 (hidden by default — enable it with 👁️ and hide another channel to keep a 3×3 grid).
- **Responsive auto-layout** — grid shape adapts to the number of visible tiles (1×1, 2×1, 2×2, 3×2, 3×3, 4×3, …) and fits the viewport with no scrolling on desktop/tablet; stacks vertically on mobile.
- **Single-audio focus** — all streams start muted; click a channel (or press `1`–`9`) to unmute just that one. Active tile gets a green border.
- **Mute all** — press `0` or `M`, or use the "Mute All" button.
- **Show / hide channels** — toggle individual channels with the 👁️ button, or use Show All / Hide All. Hidden streams are paused to save bandwidth.
- **Collapsible audio panel** — floating control panel minimizes to a small speaker icon to stay out of the way.
- **Keyboard shortcuts**
  - `1`–`9` → focus audio on channel N
  - `0` / `M` → mute all
  - `Esc` → collapse the audio panel
- **Zero dependencies** — just open `index.html` in a browser (or host as static files).

## Usage

Open `index.html` directly, or serve the folder with any static server:

```bash
python3 -m http.server 8000
# then visit http://localhost:8000
```

## Customize channels

Edit the `CHANNELS` array near the top of the `<script>` block in `index.html`:

```js
const CHANNELS = [
  { id: "VIDEO_OR_LIVE_ID", channel: "UC_CHANNEL_ID", name: "Channel Name" },
  { id: "VIDEO_OR_LIVE_ID", channel: "UC_CHANNEL_ID", name: "Optional Channel", hidden: true }, // starts hidden
  // use "live_stream?channel=CHANNEL_ID" for an always-live channel URL
];
```

## Notes

- Streams are embedded via the YouTube IFrame API; availability depends on each channel currently being live.
- Live stream IDs expire when a channel restarts its stream. If a tile's video errors or its stream ends, it automatically switches to `embed/live_stream?channel=<channel>`, which resolves to the channel's current live stream. This isn't the default because YouTube's `live_stream` embed shows "Video unavailable" for some channels (e.g. ones running several live streams at once), so a known-good video ID is still preferred.
- Autoplay policies require the page to start muted — that's why focus mode unmutes one at a time.
