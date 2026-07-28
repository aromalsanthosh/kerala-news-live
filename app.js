const grid = document.getElementById("grid");
const audioButtonsContainer = document.getElementById("audioButtons");
const audioPanel = document.getElementById("audioPanel");
const panelHeader = document.getElementById("panelHeader");
const panelSpeaker = document.getElementById("panelSpeaker");
const panelMinimize = document.getElementById("panelMinimize");
const panelStatus = document.getElementById("panelStatus");

const players = [];
const hidden = new Set();
let activeAudioIndex = -1;
let isPanelExpanded = true;

// Load YouTube IFrame API
const tag = document.createElement("script");
tag.src = "https://www.youtube.com/iframe_api";
document.head.appendChild(tag);

// Create tiles and audio buttons
CHANNELS.forEach((channel, i) => {
  const tile = document.createElement("div");
  tile.className = "tile";
  tile.id = `tile-${i}`;

  if (channel.videoId) {
    const iframe = document.createElement("iframe");
    iframe.id = `player-${i}`;
    const origin = encodeURIComponent(window.location.origin);
    iframe.src = `https://www.youtube.com/embed/${channel.videoId}?enablejsapi=1&autoplay=1&mute=1&playsinline=1&rel=0&origin=${origin}`;
    iframe.title = channel.name;
    iframe.loading = "lazy";
    iframe.referrerPolicy = "strict-origin-when-cross-origin";
    iframe.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share";
    iframe.allowFullscreen = true;
    tile.appendChild(iframe);
  } else {
    const offlineState = document.createElement("div");
    offlineState.className = "offline-state";
    offlineState.textContent = `${channel.name} is currently offline`;
    tile.appendChild(offlineState);
  }
  grid.appendChild(tile);

  const btn = document.createElement("div");
  btn.className = `audio-btn${channel.videoId ? "" : " offline"}`;
  btn.innerHTML = `
    <span class="status">${channel.videoId ? "🔇" : "⏸️"}</span>
    <span class="label">${channel.name}</span>
    <span class="index">#${i + 1}</span>
    <button class="vis-toggle" title="Hide/show this video">👁️</button>
  `;
  btn.dataset.index = i;
  btn.addEventListener("click", (event) => {
    if (event.target.classList.contains("vis-toggle")) return;
    event.stopPropagation();
    if (!channel.videoId || hidden.has(i)) return;
    setAudioFocus(i);
    if (!isPanelExpanded) expandPanel();
  });
  btn.querySelector(".vis-toggle").addEventListener("click", (event) => {
    event.stopPropagation();
    toggleVisibility(i);
  });
  audioButtonsContainer.appendChild(btn);
});

// Show All / Hide All quick actions
const actions = document.createElement("div");
actions.className = "panel-actions";
actions.innerHTML = `<button id="showAllBtn">Show All</button><button id="hideAllBtn">Hide All</button>`;
audioButtonsContainer.appendChild(actions);
actions.querySelector("#showAllBtn").addEventListener("click", (event) => {
  event.stopPropagation();
  hidden.clear();
  applyVisibility();
});
actions.querySelector("#hideAllBtn").addEventListener("click", (event) => {
  event.stopPropagation();
  CHANNELS.forEach((_, i) => hidden.add(i));
  applyVisibility();
});

// Mute All button at top
const muteAllBtn = document.createElement("button");
muteAllBtn.className = "mute-all-btn";
muteAllBtn.innerHTML = `<span class="icon">🔇</span> Mute All`;
muteAllBtn.addEventListener("click", (event) => {
  event.stopPropagation();
  setAudioFocus(-1);
});
audioButtonsContainer.insertBefore(muteAllBtn, audioButtonsContainer.firstChild);

function expandPanel() {
  if (!isPanelExpanded) {
    isPanelExpanded = true;
    audioPanel.classList.add("expanded");
    panelHeader.title = "Click speaker to minimize";
  }
}

function collapsePanel() {
  if (isPanelExpanded) {
    isPanelExpanded = false;
    audioPanel.classList.remove("expanded");
    panelHeader.title = "Click 🔊 to open audio controls";
  }
}

function togglePanel() {
  if (isPanelExpanded) collapsePanel();
  else expandPanel();
}

panelSpeaker.addEventListener("click", (event) => {
  event.stopPropagation();
  expandPanel();
});
panelMinimize.addEventListener("click", (event) => {
  event.stopPropagation();
  collapsePanel();
});
panelHeader.addEventListener("click", (event) => {
  if (
    event.target === panelHeader ||
    event.target.classList.contains("panel-title") ||
    event.target.classList.contains("panel-status")
  ) {
    togglePanel();
  }
});

function computeGridShape(n) {
  if (n <= 1) return {cols: 1, rows: 1};
  if (n === 2) return {cols: 2, rows: 1};
  if (n <= 4) return {cols: 2, rows: 2};
  if (n <= 6) return {cols: 3, rows: 2};
  if (n <= 9) return {cols: 3, rows: 3};
  if (n <= 12) return {cols: 4, rows: 3};
  const cols = Math.ceil(Math.sqrt(n));
  return {cols, rows: Math.ceil(n / cols)};
}

function applyVisibility() {
  const visibleCount = CHANNELS.length - hidden.size;
  document.querySelectorAll(".tile").forEach((tile, i) => {
    tile.classList.toggle("hidden", hidden.has(i));
  });
  document.querySelectorAll(".audio-btn").forEach((btn, i) => {
    btn.classList.toggle("is-hidden", hidden.has(i));
    const toggle = btn.querySelector(".vis-toggle");
    if (toggle) toggle.textContent = hidden.has(i) ? "🙈" : "👁️";
  });
  const {cols, rows} = computeGridShape(visibleCount);
  grid.style.setProperty("--cols", cols);
  grid.style.setProperty("--rows", rows);

  if (activeAudioIndex !== -1 && hidden.has(activeAudioIndex)) {
    setAudioFocus(-1);
  }
  players.forEach((player, i) => {
    if (!player?.playVideo) return;
    try {
      if (hidden.has(i)) player.pauseVideo();
      else player.playVideo();
    } catch (_) {}
  });
}

function toggleVisibility(i) {
  if (hidden.has(i)) hidden.delete(i);
  else hidden.add(i);
  applyVisibility();
}

function setAudioFocus(index) {
  activeAudioIndex = index;
  document.querySelectorAll(".audio-btn").forEach((btn, i) => {
    const status = btn.querySelector(".status");
    if (!CHANNELS[i].videoId) {
      status.textContent = "⏸️";
      return;
    }
    if (i === index) {
      btn.classList.add("active");
      status.textContent = "🔊";
    } else {
      btn.classList.remove("active");
      status.textContent = "🔇";
    }
  });
  document.querySelectorAll(".tile").forEach((tile, i) => {
    tile.classList.toggle("active-audio", i === index);
  });
  panelStatus.textContent = index === -1 ? "All muted" : `Playing: ${CHANNELS[index].name}`;
  players.forEach((player, i) => {
    if (!player?.mute) return;
    if (i === index) {
      player.unMute();
      player.setVolume(100);
    } else {
      player.mute();
    }
  });
}

window.onYouTubeIframeAPIReady = function () {
  CHANNELS.forEach((channel, i) => {
    if (!channel.videoId) return;
    new YT.Player(`player-${i}`, {
      events: {
        onReady: (event) => {
          players[i] = event.target;
          event.target.mute();
        }
      }
    });
  });
};

document.addEventListener("keydown", (event) => {
  if (event.target.tagName === "INPUT" || event.target.tagName === "TEXTAREA") return;
  const key = event.key;
  if (/^[1-9]$/.test(key)) {
    const index = parseInt(key, 10) - 1;
    if (index < CHANNELS.length && CHANNELS[index].videoId && !hidden.has(index)) {
      event.preventDefault();
      setAudioFocus(index);
      if (!isPanelExpanded) expandPanel();
    }
  }
  if (key === "0" || key.toLowerCase() === "m") {
    event.preventDefault();
    setAudioFocus(-1);
  }
  if (key === "Escape" && isPanelExpanded) collapsePanel();
});

setAudioFocus(-1);
