# 🎬 TwinVine — Unified Video + PDF Capture System

> **Automated DRM video downloader with intelligent PDF capture.** Uses browser extension to capture both video URLs and PDF documents from Testbook lessons, extracts Widevine keys immediately, then downloads everything with a unified queue system.

---

## ✨ Features

| Feature | Details |
|---|---|
| 🤖 **Fully Automated** | Play video + navigate lesson — extension captures everything silently |
| 📄 **Smart PDF Capture** | Automatically detects and queues PDF documents (no download prompts) |
| 🔄 **Unified Queue** | Single entries containing both video + PDF data for each lesson |
| 🔑 **Instant Key Extraction** | DRM keys extracted immediately so tokens never expire |
| ⚡ **Parallel Downloads** | Download 3–5 lessons simultaneously with both video and PDF |
| 📝 **Smart Title Detection** | Lesson names auto-extracted and cleaned from page DOM |
| 🛡️ **Zero User Prompts** | No "Save As" dialogs — everything happens in background |
| 🏗️ **Modular Architecture** | Clean, maintainable codebase with separation of concerns |

---

## 🚀 Quick Setup

### 1. Prerequisites
```bash
# Install Python dependencies
uv pip install -e .

# Place your Widevine L3 device credentials:
#   ./WVDs/device.wvd

# Install external tools (macOS):
brew install ffmpeg bento4
# Download N_m3u8DL-RE binary → place in ./bin/N_m3u8DL-RE
```

### 2. Load Browser Extension v1.2.0
```
1. Open chrome://extensions/
2. Enable "Developer mode"
3. Click "Load unpacked" → select browser-extension/ folder
4. Pin TwinVine to your toolbar
```

---

## 📖 Workflow

### Step 1 — Start the server
```bash
# Start the unified capture server
python twinvine_server.py
# or
uv run python twinvine_server.py
```
Server runs on `http://localhost:8765` — keep this running during capture.

### Step 2 — Capture lessons automatically
1. Navigate to any Testbook lesson page
2. Play the video for **≥ 10 seconds** 
3. Extension automatically:
   - 📄 Detects PDF URLs in iframes (no downloads)
   - 🎬 Captures video MPD when playing
   - 🔑 Extracts DRM keys immediately
   - 🔄 Merges PDF + video into single queue entries

### Step 3 — Download everything
```bash
# Check what was captured
python twinvine.py status

# Download all lessons in parallel
python twinvine.py download --workers 5
```

**Result:** 720p MP4 files + PDF documents organized in `./downloads/` 🎉
python twinvine.py server
```
The popup will show a **green dot** when the server is connected.

### Step 2 — Capture lessons
Open each Testbook lesson and play for **≥ 10 seconds**.  
The extension captures the URLs silently, extracts keys immediately, and increments the badge count.

### Step 3 — Download everything
```bash
# Check what was captured
python twinvine.py status

# Download all in parallel (adjust workers to your internet speed)
python twinvine.py download --workers 5
```

**Done!** 🎉 720p MP4 files land in `./downloads/`.

---

## 🛠️ All Commands

```bash
python twinvine.py server              # Start capture server (port 8765)
python twinvine.py status              # Show queue
python twinvine.py download            # Download all pending videos
python twinvine.py download --workers 5  # Parallel downloads (default: 3)
python twinvine.py retry               # Retry any failed downloads
python twinvine.py single              # Manually download one video
python twinvine.py clear               # Clear the queue

# Change server port:
TWINVINE_PORT=9000 python twinvine.py server
```

---

## 📁 Project Structure

```
twinvine.py           # ← Primary entry point (server + download + status)
twinvine_core.py      # ← Shared DRM & download logic
browser-extension/
  background.js       # Service worker — URL capture + smart title extraction
  popup.html/js       # Popup UI with live server health dot
  manifest.json       # Manifest V3, v1.1
WVDs/                 # Widevine credentials (gitignored)
vaults/course_cache/  # Captured queue JSON (gitignored)
downloads/            # Output MP4 files (gitignored)
bin/                  # Place N_m3u8DL-RE here if not in PATH
```

---

## 🔧 Configuration

| Setting | How |
|---|---|
| Server port | `TWINVINE_PORT=9000` env var |
| Parallel workers | `--workers N` flag |
| WVD path | `./WVDs/device.wvd` (hardcoded, editable in `twinvine_core.py`) |

---

## 🔒 Privacy

- ✅ **100% local** — no external services, no telemetry
- ✅ **Your credentials** — uses your own WVD device file
- ✅ **Open source** — all code reviewable

---

## ⚙️ Requirements

- Python 3.10 – 3.12
- Chrome / Edge / Brave
- `ffmpeg`, `mp4decrypt` (bento4), `N_m3u8DL-RE`
- Widevine L3 device credentials (`device.wvd`)

---

**Version:** 2.0  |  **Status:** ✅ Production Ready  |  **Updated:** 2026-02-21
