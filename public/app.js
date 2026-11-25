:root {
  --bg: #090909;
  --surface: #121316;
  --surface-2: #191b20;
  --border: #252830;
  --text: #f5f5f5;
  --muted: #9ca3af;
  --accent: #22c55e;
  --accent-soft: rgba(34, 197, 94, 0.14);
}

* { box-sizing: border-box; }

html, body {
  margin: 0;
  padding: 0;
  background: var(--bg);
  color: var(--text);
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

svg {
  width: 20px;
  height: 20px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

/* Auth Overlay */
.auth-overlay {
  position: fixed;
  inset: 0;
  background: rgba(9, 9, 9, 0.96);
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 18px;
}

.auth-overlay.hidden { display: none; }

.auth-box {
  width: 100%;
  max-width: 420px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 20px;
}

.auth-box h2 { margin: 0 0 6px; }
.auth-sub { margin: 0 0 14px; color: var(--muted); font-size: 0.9rem; }

.auth-box input {
  width: 100%;
  background: var(--bg);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 11px 12px;
  margin-bottom: 10px;
  font-size: 0.95rem;
}

.auth-actions { display: flex; gap: 8px; }
.auth-actions button {
  flex: 1;
  padding: 11px 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--accent);
  color: #051109;
  font-weight: 700;
  cursor: pointer;
}

.auth-actions .ghost-btn {
  background: var(--surface-2);
  color: var(--text);
}

.hash-box {
  margin-top: 12px;
  padding: 10px;
  background: var(--bg);
  border: 1px dashed var(--border);
  border-radius: 8px;
  font-size: 0.78rem;
}

.hash-box span { display: block; color: var(--muted); margin-bottom: 4px; }
.hash-box code { word-break: break-all; color: #86efac; }
.auth-status { margin: 10px 0 0; font-size: 0.84rem; color: var(--muted); }

/* Topbar */
.topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: rgba(9, 9, 9, 0.9);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--border);
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--text);
  text-decoration: none;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.brand-mark {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: var(--accent);
  color: #051109;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 900;
}

.room-badge {
  font-size: 0.72rem;
  font-weight: 700;
  padding: 5px 10px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  border: 1px solid rgba(34, 197, 94, 0.3);
}

/* Main & Pages */
.app-main {
  max-width: 680px;
  margin: 0 auto;
  padding: 18px 16px 96px;
}

.page { display: none; }
.page.active { display: block; }

.eyebrow {
  margin: 0 0 4px;
  font-size: 0.72rem;
  letter-spacing: 0.12em;
  color: var(--accent);
  font-weight: 700;
}

h1 { margin: 0 0 6px; font-size: 1.8rem; }
h1 span { color: var(--accent); }
.welcome p { margin: 0; color: var(--muted); }

.section-heading, .results-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 20px 0 10px;
}

.section-heading h2, .results-heading h2 {
  margin: 0;
  font-size: 0.8rem;
  letter-spacing: 0.08em;
  color: var(--muted);
}

.playing-status { font-size: 0.75rem; font-weight: 700; color: var(--accent); }

/* Player Card */
.player-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 14px;
}

.video-frame {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: 12px;
  overflow: hidden;
  background: #050506;
  border: 1px solid var(--border);
}

.video-frame iframe,
.video-frame #youtubePlayer {
  width: 100%;
  height: 100%;
  display: block;
  transform-origin: center center;
  transition: transform 0.2s ease;
}

/* Keep a small visible thumbnail/frame even in audio-focused mode */
.player-card.audio-mode .video-frame {
  aspect-ratio: 16 / 5;
}

.video-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: var(--muted);
  background: #0b0c0e;
  pointer-events: none;
}

.video-placeholder.hidden { display: none; }

.track-info { margin: 12px 0 8px; }
.track-info h2 { margin: 0; font-size: 1.05rem; }
.track-info p { margin: 3px 0 0; font-size: 0.86rem; color: var(--muted); }

.progress-area {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.75rem;
  color: var(--muted);
  margin: 10px 0;
}

#seekBar { flex: 1; accent-color: var(--accent); cursor: pointer; }

.player-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin: 12px 0;
}

.icon-button {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface-2);
  color: var(--text);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.icon-button.active {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-soft);
}

.icon-button.main-play {
  width: 54px;
  height: 54px;
  border-radius: 999px;
  background: var(--accent);
  color: #051109;
  border: none;
}

.icon-button.main-play svg { fill: currentColor; stroke: none; }

.video-mode-button {
  width: 100%;
  padding: 10px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface-2);
  color: var(--text);
  font-weight: 700;
  font-size: 0.8rem;
  letter-spacing: 0.06em;
  cursor: pointer;
}

.zoom-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
  font-size: 0.75rem;
  color: var(--muted);
}

.zoom-controls > div { display: flex; gap: 6px; }

.small-icon {
  padding: 5px 10px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface-2);
  color: var(--text);
  font-size: 0.78rem;
  cursor: pointer;
}

/* Home Feature Cards */
.home-actions { display: grid; gap: 10px; margin-top: 16px; }

.feature-card {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  text-align: left;
  cursor: pointer;
}

.feature-icon {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: var(--accent-soft);
  color: var(--accent);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.feature-card b { display: block; font-size: 0.95rem; }
.feature-card small { color: var(--muted); font-size: 0.8rem; }
.feature-arrow { margin-left: auto; font-size: 1.3rem; color: var(--muted); }

/* Search & Playlist Inputs */
.search-box, .create-playlist-box {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 6px 8px 6px 12px;
}

.search-box input, .create-playlist-box input {
  flex: 1;
  min-width: 0;
  border: none;
  background: transparent;
  color: var(--text);
  font-size: 0.95rem;
  outline: none;
}

.search-box button, .create-playlist-box button {
  width: 38px;
  height: 38px;
  border-radius: 9px;
  border: none;
  background: var(--accent);
  color: #051109;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.status-text { color: var(--muted); font-size: 0.85rem; }

.text-button {
  background: var(--surface-2);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 0.72rem;
  font-weight: 700;
  cursor: pointer;
}

/* Song & Playlist Lists */
.song-list { display: grid; gap: 10px; }

.song-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
}

.song-item img {
  width: 58px;
  height: 44px;
  object-fit: cover;
  border-radius: 6px;
  flex-shrink: 0;
}

.song-meta { flex: 1; min-width: 0; }
.song-title {
  font-size: 0.9rem;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.song-channel { font-size: 0.78rem; color: var(--muted); }

.song-actions { display: flex; gap: 6px; }
.song-actions button {
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface-2);
  color: var(--text);
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
}
.song-actions button.primary {
  background: var(--accent);
  color: #051109;
  border: none;
  font-weight: 700;
}

/* Settings */
.settings-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 16px;
  margin-bottom: 12px;
}

.settings-icon {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: var(--accent-soft);
  color: var(--accent);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 10px;
}

.settings-card h2 { margin: 0 0 4px; font-size: 1rem; }
.settings-card p { margin: 0 0 10px; color: var(--muted); font-size: 0.88rem; }

.settings-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-top: 1px solid var(--border);
  font-size: 0.86rem;
}

/* Bottom Navigation */
.bottom-nav {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 30;
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  background: rgba(12, 13, 16, 0.96);
  backdrop-filter: blur(10px);
  border-top: 1px solid var(--border);
  padding: 6px 4px calc(6px + env(safe-area-inset-bottom));
}

.nav-item {
  background: transparent;
  border: none;
  color: var(--muted);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  font-size: 0.65rem;
  font-weight: 700;
  padding: 6px 2px;
  cursor: pointer;
}

.nav-item.active { color: var(--accent); }
