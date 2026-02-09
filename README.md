# 🎬 TwinVine - Automated DRM Video Downloader

**The ultimate solution for downloading DRM-protected content from Testbook.**

Fully automated course downloading with parallel processing and maximum speed!

---

## ✨ Features

- 🚀 **Fully Automated** - Just play videos, extension captures everything
- 🔑 **Auto Key Extraction** - Keys extracted immediately (no token expiration)
- ⚡ **Parallel Downloads** - Download 3-5 videos simultaneously
- 📊 **Smart Metadata** - Auto-detects titles and durations
- 🎯 **One Command** - Download entire courses with one command
- 💾 **Auto Cleanup** - Intermediate files cleaned automatically
- 🎬 **720p HD Quality** - Best available quality

---

## 🚀 Quick Start

### **1. Install Extension**
```
1. Open chrome://extensions/
2. Enable "Developer mode"
3. Click "Load unpacked"
4. Select: TwinVine/browser-extension/
5. Pin extension to toolbar
```

### **2. Start Auto-Capture Server**
```bash
# Install dependencies (first time only)
uv pip install flask flask-cors

# Start server
python twinvine_server.py
```

### **3. Capture Course**
```
1. Open Testbook course
2. Play each video briefly (10 seconds)
3. Extension auto-captures URLs
4. Server extracts keys immediately
5. Badge shows count (1, 2, 3...)
```

### **4. Download All**
```bash
# Check status
python twinvine_auto.py status

# Download all in parallel (5 simultaneous)
python twinvine_auto.py download --workers 5
```

**Done!** 🎉

---

## 📖 Complete Workflow

### **For a 20-Lesson Course:**

```bash
# Terminal 1: Start server (keep running)
python twinvine_server.py

# Browser: Capture all lessons (5-10 min)
# - Open lesson 1 → Play 10 sec → Badge shows "1"
# - Open lesson 2 → Play 10 sec → Badge shows "2"
# - ... continue for all 20 lessons ...
# - Badge shows "20" when done!

# Terminal 2: Download all (1.5 hours, automated)
python twinvine_auto.py download --workers 5

# Result: 20 ready-to-play 720p MP4 files!
```

---

## 🎯 Available Tools

### **🌟 AUTO MODE (Recommended)**

**Fully automated course downloading:**

```bash
# Start server
python twinvine_server.py

# Browse course, play each video 10 sec
# Extension auto-captures everything

# Download all
python twinvine_auto.py download --workers 5
```

**Best for:** Complete courses, maximum automation

---

### **⚡ PARALLEL MODE**

**Manual capture, parallel download:**

```bash
# Capture keys manually
python twinvine_parallel.py capture

# Download in parallel
python twinvine_parallel.py download --workers 5
```

**Best for:** When auto-capture isn't working

---

### **📹 SINGLE VIDEO MODE**

**Download one video at a time:**

```bash
python twinvine_720p.py

# Paste MPD URL
# Paste License URL
# Enter filename
# Downloads automatically
```

**Best for:** Individual videos, testing

---

## 📊 Speed Comparison

### **20-Lesson Course (1 hour each):**

| Method | Time | Speed |
|--------|------|-------|
| **Manual Sequential** | ~6 hours | 1x |
| **Manual Parallel** | ~2 hours | 3x faster ⚡ |
| **Auto Mode** | ~1.5 hours | **4x faster** 🚀 |

**Auto Mode Breakdown:**
- Capture: 10 min (just play videos)
- Download: 1.5 hours (parallel, automated)
- **Total active time: 10 minutes!**

---

## 🛠️ Commands Reference

### **Auto Mode:**
```bash
# Start server
python twinvine_server.py

# Check queue
python twinvine_auto.py status

# Download all
python twinvine_auto.py download [--workers N]

# Clear queue
python twinvine_auto.py clear
```

### **Parallel Mode:**
```bash
# Capture keys
python twinvine_parallel.py capture

# Download all
python twinvine_parallel.py download [--workers N]

# Check status
python twinvine_parallel.py status
```

### **Single Video:**
```bash
# Interactive mode
python twinvine_720p.py
```

---

## 📁 Project Structure

```
TwinVine/
├── twinvine_server.py          # Auto-capture server ⭐
├── twinvine_auto.py             # Auto downloader ⭐
├── twinvine_parallel.py         # Parallel downloader
├── twinvine_720p.py             # Single video downloader
│
├── browser-extension/           # Browser extension ⭐
│   ├── manifest.json
│   ├── background.js           # Auto-capture logic
│   ├── popup.html              # Extension UI
│   ├── popup.js
│   └── icon*.png
│
├── WVDs/                        # Widevine credentials
│   └── device.wvd              # Required!
│
├── vaults/                      # Cached data
│   ├── course_cache/           # Auto-captured queue
│   └── *_keys.txt              # Cached keys
│
├── downloads/                   # Downloaded videos
│   └── *_720p_FINAL.mp4
│
├── README.md                    # This file
├── AUTO_MODE_GUIDE.md          # Detailed auto mode guide
└── PARALLEL_DOWNLOAD_GUIDE.md  # Parallel mode guide
```

---

## 🔧 Configuration

### **Parallel Workers:**

Adjust based on your internet speed:

```bash
# Fast internet (100+ Mbps)
--workers 5

# Normal internet (50-100 Mbps)
--workers 3  # default

# Slow internet (<50 Mbps)
--workers 2
```

### **WVD File:**

Required for key extraction. Place at `./WVDs/device.wvd`

---

## 🎓 How It Works

### **Auto Mode Architecture:**

```
Browser Extension          Local Server          Download Script
━━━━━━━━━━━━━━━          ━━━━━━━━━━━━          ━━━━━━━━━━━━━━━
1. Detects URLs    →      2. Extracts Keys →    3. Downloads Videos
   (Real-time)               (Immediate)           (Parallel)

MPD + License URLs  →  Widevine L3 Keys  →  720p MP4 Files
```

### **Why It's Fast:**

1. **Parallel downloads** - 3-5 videos at once
2. **Immediate key extraction** - No token expiration
3. **Smart caching** - Keys reused if needed
4. **Auto cleanup** - No manual file management

---

## 💡 Tips & Best Practices

### **Capture Phase:**
- ✅ Start server before browsing
- ✅ Play each video 10 seconds (enough for capture)
- ✅ Watch badge count to confirm
- ✅ Capture all lessons in one session

### **Download Phase:**
- ✅ Close browser to free bandwidth
- ✅ Use stable internet connection
- ✅ Adjust workers based on speed
- ✅ Run overnight for large courses

### **Troubleshooting:**
- Server not receiving? Check localhost:8765
- Keys not extracting? Check WVD file exists
- Downloads failing? Reduce workers

---

## 🎊 Success Story

**Before TwinVine:**
- ⏰ 6+ hours for 20-lesson course
- 😫 Manual URL copying for each video
- 🐌 Sequential downloads (one at a time)
- 😤 Token expiration issues
- 📝 Manual filename entry

**After TwinVine:**
- ⚡ 1.5 hours for 20-lesson course (4x faster!)
- 😎 Just play videos (10 sec each)
- 🚀 Parallel downloads (5 at once)
- ✅ No token issues (keys cached)
- 🤖 Auto-generated filenames

**Total active time: 10 minutes vs 6+ hours!**

---

## 📚 Documentation

- **AUTO_MODE_GUIDE.md** - Complete auto mode guide
- **PARALLEL_DOWNLOAD_GUIDE.md** - Parallel mode details
- **browser-extension/README.md** - Extension documentation

---

## 🔒 Privacy & Security

- ✅ **100% Local** - All processing on your machine
- ✅ **No Cloud** - No external services
- ✅ **No Tracking** - No analytics or telemetry
- ✅ **Open Source** - Review all code
- ✅ **Your Credentials** - Uses your own WVD file

---

## ⚙️ Requirements

- Python 3.8+
- Chrome/Edge/Brave browser
- Widevine L3 credentials (device.wvd)
- Dependencies: `flask`, `flask-cors`, `pywidevine`, `requests`

---

## 🎯 Summary

**TwinVine is the complete solution for downloading DRM-protected courses:**

✅ **Fully automated** - Minimal manual work  
✅ **Maximum speed** - Parallel downloads  
✅ **No token issues** - Immediate key extraction  
✅ **Professional quality** - 720p HD  
✅ **Easy to use** - Simple commands  
✅ **Production ready** - Tested and reliable  

**Perfect for downloading entire courses efficiently!** 🚀

---

**Version:** 5.0 - AUTO MODE  
**Status:** ✅ Production Ready  
**Last Updated:** 2026-02-09

---

## 🚀 Get Started

```bash
# 1. Start server
python twinvine_server.py

# 2. Browse course, play each video 10 sec

# 3. Download all
python twinvine_auto.py download --workers 5
```

**Enjoy effortless course downloading!** 🎉
