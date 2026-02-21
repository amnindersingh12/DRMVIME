# 🎬 TwinVine Browser Extension

**Automatically captures MPD and License URLs from Testbook videos!**

## ✨ Features

- ✅ **Automatic URL Detection** - Captures URLs as you play videos
- ✅ **Real-time Updates** - Shows status in popup
- ✅ **One-Click Copy** - Copy both URLs to clipboard
- ✅ **Visual Indicators** - Badge shows when URLs are captured
- ✅ **Clean Interface** - Beautiful, easy-to-use popup

---

## 🚀 Installation

### **Chrome/Edge/Brave:**

1. **Open Extensions Page**
   - Chrome: `chrome://extensions/`
   - Edge: `edge://extensions/`
   - Brave: `brave://extensions/`

2. **Enable Developer Mode**
   - Toggle the switch in the top-right corner

3. **Load Extension**
   - Click "Load unpacked"
   - Select the `browser-extension` folder
   - Extension will appear in your toolbar

4. **Pin Extension** (Optional)
   - Click the puzzle icon in toolbar
   - Pin "TwinVine URL Capturer"

---

## 📖 How to Use

### **Step 1: Open Testbook Lesson**
```
1. Go to Testbook
2. Open any video lesson
3. The extension is now monitoring
```

### **Step 2: Play Video**
```
1. Click play on the video
2. Extension automatically captures:
   - MPD URL (manifest)
   - License URL (with token)
3. Badge shows "BOTH" when ready
```

### **Step 3: Copy URLs**
```
1. Click extension icon
2. See captured URLs
3. Click "Copy Both"
4. URLs copied to clipboard!
```

### **Step 4: Use in TwinVine**
```
1. Run: uv run python twinvine_720p.py
2. Paste MPD URL when prompted
3. Paste License URL when prompted
4. Download starts automatically!
```

---

## 🎯 Visual Guide

### **Extension Badge:**
- **Empty** - Waiting for video
- **MPD** - MPD URL captured
- **BOTH** - Both URLs captured ✅

### **Popup Status:**
- ⏳ **Waiting...** - Not captured yet
- ✅ **Captured!** - URL is ready

### **Popup Display:**
```
🎬 TwinVine URL Capturer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📄 MPD URL: ✅ Captured!
🔐 License URL: ✅ Captured!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📄 MPD URL:
https://mediacdn.testbook.com/.../lesson.mpd

🔐 License URL:
https://india-drm.sdmc.tv/getlicense?token=...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[📋 Copy Both]  [🗑️ Clear]
```

---

## 🔧 Complete Workflow

### **Download Single Video:**
```bash
# 1. Open Testbook lesson
# 2. Play video
# 3. Click extension → "Copy Both"
# 4. Run downloader:

uv run python twinvine_720p.py

# 5. Paste URLs (Cmd+V)
# 6. Done!
```

### **Batch Download Course:**
```bash
# 1. Run downloader:
uv run python twinvine_720p.py

# For each lesson:
# 2. Open lesson in browser
# 3. Play video
# 4. Click extension → "Copy Both"
# 5. Paste URLs in terminal
# 6. Answer 'y' to download another
# 7. Repeat for all lessons
```

---

## 💡 Pro Tips

1. **Keep extension pinned** - Quick access to captured URLs
2. **Clear after each video** - Click "Clear" before next lesson
3. **Watch the badge** - Wait for "BOTH" before copying
4. **Fresh tokens** - Each video needs its own license URL
5. **Batch mode** - Use with TwinVine's batch download feature

---

## 🛠️ Technical Details

### **What it Captures:**
```javascript
// MPD URL
Pattern: *.mpd
Domain: mediacdn.testbook.com
Example: .../hash/hash.mpd

// License URL
Pattern: */getlicense?token=*
Domain: india-drm.sdmc.tv
Example: .../getlicense?token=eyJ...
```

### **How it Works:**
```
Browser Network Request
    ↓
Extension monitors webRequest API
    ↓
Matches URL patterns
    ↓
Stores in chrome.storage
    ↓
Updates popup UI
    ↓
User clicks "Copy Both"
    ↓
Clipboard ready for TwinVine!
```

---

## 🔒 Privacy & Security

- ✅ **No data sent externally** - Everything stays local
- ✅ **Only monitors Testbook domains** - Restricted permissions
- ✅ **No tracking** - No analytics or telemetry
- ✅ **Open source** - You can review all code
- ✅ **Clipboard only** - Data only copied when you click

---

## 🎊 Benefits

| Before | After |
|--------|-------|
| Open DevTools | Just play video |
| Find Network tab | Extension auto-captures |
| Filter requests | Click extension icon |
| Find .mpd file | See both URLs |
| Copy URL | Click "Copy Both" |
| Find getlicense | Paste in terminal |
| Copy URL | Done! |
| Paste both manually | **5 seconds total** |
| **~2 minutes** | |

**90% faster workflow!** 🚀

---

## 📁 Files

```
browser-extension/
├── manifest.json      # Extension config
├── background.js      # URL capture logic
├── popup.html         # UI interface
├── popup.js           # UI logic
└── README.md          # This file
```

---

## 🐛 Troubleshooting

### **URLs not captured:**
- Make sure video is playing
- Check extension is enabled
- Refresh the page and try again

### **"Copy Both" disabled:**
- Wait for both URLs to be captured
- Badge should show "BOTH"

### **Token expired:**
- Tokens expire in 2-5 minutes
- Capture fresh URLs for each download

---

## 🎓 Example Session

```bash
# Terminal:
$ uv run python twinvine_720p.py

# Browser:
1. Open lesson 1 → Play video
2. Click extension → "Copy Both"

# Terminal:
📍 Paste MPD URL: [Cmd+V]
🔐 Paste License URL: [Cmd+V]
✅ Downloaded lesson 1!
📥 Download another? y

# Browser:
3. Open lesson 2 → Play video
4. Click extension → "Clear" → "Copy Both"

# Terminal:
📍 Paste MPD URL: [Cmd+V]
🔐 Paste License URL: [Cmd+V]
✅ Downloaded lesson 2!
📥 Download another? n

🎉 Complete! Downloaded 2 videos
```

---

## ✅ Summary

**TwinVine Browser Extension** makes downloading effortless:
- ✅ Automatic URL capture
- ✅ One-click copy
- ✅ Real-time updates
- ✅ Clean interface
- ✅ 90% faster workflow

**Perfect companion for TwinVine downloader!** 🚀

---

**Version:** 1.0  
**Compatible:** Chrome, Edge, Brave, Opera  
**Status:** ✅ Ready to use
