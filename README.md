# TwinVine - Widevine L3 DRM Downloader

**A professional tool for downloading and decrypting DRM-protected content using Widevine L3 key extraction.**

---

## 🎯 What This Does

Downloads DRM-protected videos (like Testbook lessons) by:
1. **Extracting decryption keys** from the license server
2. **Downloading encrypted streams** (video + audio)
3. **Decrypting the files** using extracted keys
4. **Merging** into a single playable 720p MP4

---

## ⚡ Quick Start

```bash
# Run the downloader
uv run python twinvine_720p.py
```

**You'll need:**
1. **MPD URL** - The video manifest (ends with `.mpd`)
2. **License URL** - The license server URL with token

**How to get these:**
1. Open video in browser
2. Press F12 → Network tab
3. Play the video
4. Find MPD URL (filter: `.mpd`)
5. Find License URL (filter: `getlicense`)
6. Copy both and paste when prompted

---

## 🔧 How It Works - Technical Implementation

### **Architecture Overview**

```
Browser (User) → URLs → TwinVine Script
    ↓
[1] Key Extraction (pywidevine)
    ↓
[2] Download (N_m3u8DL-RE)
    ↓
[3] Decryption (mp4decrypt)
    ↓
[4] Merge (ffmpeg)
    ↓
Final 720p MP4 ✅
```

---

## 📚 Implementation Details

### **1. Key Extraction - Widevine CDM Protocol**

**Tool Used:** `pywidevine` (Python Widevine CDM library)

**How it works:**
```python
# Step 1: Extract PSSH from MPD
# PSSH = Protection System Specific Header (contains Key IDs)
pssh = extract_from_mpd(mpd_url)

# Step 2: Load WVD device credentials
# WVD = Widevine Device file (contains private key + client ID)
device = Device.load("./WVDs/device.wvd")

# Step 3: Create CDM (Content Decryption Module)
cdm = Cdm.from_device(device)

# Step 4: Generate license challenge
# Challenge = encrypted request with device credentials
challenge = cdm.get_license_challenge(session_id, pssh)

# Step 5: Send to license server
# Server validates device and returns encrypted keys
response = requests.post(license_url, data=challenge)

# Step 6: Parse license and extract keys
cdm.parse_license(session_id, response.content)
keys = cdm.get_keys(session_id)  # Returns: KID:KEY pairs
```

**Why this works:**
- Widevine L3 is **software-based** (keys in memory, not secure hardware)
- WVD file contains valid device credentials
- License server can't distinguish between real device and pywidevine
- Keys are returned encrypted, but CDM decrypts them using device private key

**Output:** Decryption keys in format `KID:KEY` (hex strings)
```
73cfec265a0ef95c4fe4f8e2c3892838:e090de721fbd0479a8dfa23ffc8e8cf6
d0b8a44b9fb931b49b1cb54c52a75047:1e7127498704fc8e2d3b97b480a969ff
```

---

### **2. Download - DASH Stream Downloading**

**Tool Used:** `N_m3u8DL-RE` (DASH/HLS downloader)

**How it works:**
```bash
N_m3u8DL-RE <mpd_url> \
  --auto-select \              # Select best video + audio
  --binary-merge \             # Merge segments
  --key KID1:KEY1 \           # Provide decryption keys
  --key KID2:KEY2 \
  -mt                          # Multi-threaded download
```

**What it does:**
1. Parses MPD manifest to find stream URLs
2. Selects best quality streams (720p video + audio)
3. Downloads encrypted segments in parallel
4. Merges segments into single files

**Output:** 
- `video.mp4` (encrypted, 720p)
- `audio.m4a` (encrypted)

**Note:** N_m3u8DL-RE downloads but doesn't decrypt (our version doesn't support `--key-server`)

---

### **3. Decryption - MP4 File Decryption**

**Tool Used:** `mp4decrypt` (Bento4 toolkit)

**How it works:**
```bash
mp4decrypt \
  --key KID1:KEY1 \
  --key KID2:KEY2 \
  --key KID3:KEY3 \
  input_encrypted.mp4 \
  output_decrypted.mp4
```

**What it does:**
1. Reads encrypted MP4 file
2. Identifies encrypted samples (marked with `cenc` protection)
3. Uses provided keys to decrypt each sample
4. Writes decrypted samples to new file

**Technical details:**
- Uses AES-128-CTR decryption
- Each segment has its own IV (Initialization Vector)
- KID (Key ID) identifies which key to use for each track
- Preserves video/audio codec (no re-encoding)

**Output:**
- `video_decrypted.mp4` (playable video, no audio)
- `audio_decrypted.m4a` (playable audio)

---

### **4. Merge - Audio/Video Combination**

**Tool Used:** `ffmpeg` (multimedia framework)

**How it works:**
```bash
ffmpeg \
  -i video_decrypted.mp4 \    # Input video
  -i audio_decrypted.m4a \    # Input audio
  -c copy \                    # Copy streams (no re-encode)
  -map 0:v:0 \                # Map video from input 0
  -map 1:a:0 \                # Map audio from input 1
  output_final.mp4
```

**What it does:**
1. Reads video stream from first input
2. Reads audio stream from second input
3. Copies both streams without re-encoding (fast!)
4. Muxes into single MP4 container

**Output:** `*_720p_FINAL.mp4` (complete playable video)

---

## 🔑 Key Components Explained

### **WVD File (Widevine Device)**
```
WVDs/device.wvd
```
Contains:
- **Device Private Key** - RSA key for decrypting license responses
- **Client ID Blob** - Device identification
- **VMP Blob** - Verified Media Path data (optional)

**How to get:** Extract from Android device or emulator (requires root)

---

### **PSSH (Protection System Specific Header)**
Found in MPD manifest:
```xml
<cenc:pssh>AAAAXHBzc2gAAAAA7e+LqXnWSs6jyCfc1R0h7QAAADw...</cenc:pssh>
```

Contains:
- System ID (Widevine UUID)
- Key IDs for all tracks
- Initialization data

**Purpose:** Tells CDM which keys to request from license server

---

### **License Challenge/Response**
**Challenge (sent to server):**
- Encrypted with server public key
- Contains: PSSH, device credentials, random session data

**Response (from server):**
- Encrypted with device public key
- Contains: Content keys, usage policies, expiration

**CDM decrypts response using device private key**

---

### **Key Format**
```
KID:KEY
73cfec265a0ef95c4fe4f8e2c3892838:e090de721fbd0479a8dfa23ffc8e8cf6
└─────────── 32 hex chars ───────────┘ └─────────── 32 hex chars ───────────┘
        (16 bytes)                              (16 bytes)
```

- **KID** (Key ID) - Identifies which track this key decrypts
- **KEY** - AES-128 decryption key

---

## 🛠️ Tools Stack

| Tool | Purpose | Why This One |
|------|---------|--------------|
| **pywidevine** | Widevine CDM | Pure Python, no device needed |
| **N_m3u8DL-RE** | DASH downloader | Fast, multi-threaded, supports DASH |
| **mp4decrypt** | MP4 decryption | Industry standard, reliable |
| **ffmpeg** | A/V merging | Universal, lossless copy |

---

## 📁 Project Structure

```
TwinVine/
├── twinvine_720p.py          # Main script (ONLY file you need)
├── README.md                  # This file
├── .gitignore                 # Git ignore rules
│
├── WVDs/                      # Widevine device credentials
│   └── device.wvd            # Your L3 device file
│
├── vaults/                    # Cached decryption keys
│   └── testbook_keys_latest.txt
│
└── downloads/                 # Output videos
    └── *_720p_FINAL.mp4      # Ready to play
```

**That's it! No bloat, just essentials.**

---

## 🎬 Complete Workflow Example

```bash
$ uv run python twinvine_720p.py

📍 Paste MPD URL: https://mediacdn.testbook.com/.../lesson.mpd
🔐 Paste License URL: https://india-drm.sdmc.tv/getlicense?token=...
Enter filename: physics_lesson

# [1] KEY EXTRACTION
🔑 Extracting decryption keys...
📥 Fetching MPD...
✅ Found PSSH
📱 Loading device: ./WVDs/device.wvd
🔓 CDM session opened
📤 Generated license challenge (2123 bytes)
🌐 Requesting license from server...
✅ Received license (1039 bytes)
🔑 73cfec265a0ef95c4fe4f8e2c3892838:e090de721fbd0479a8dfa23ffc8e8cf6
🔑 d0b8a44b9fb931b49b1cb54c52a75047:1e7127498704fc8e2d3b97b480a969ff
🔑 e181c4fa28cf8ab4b751feaf46cec362:8ef27494f9bc65353b020c5c57d7d892
💾 Keys cached to: vaults/testbook_keys_latest.txt

# [2] DOWNLOAD
📦 Starting download with N_m3u8DL-RE...
🚀 Downloading 720p video to: ./downloads/physics_lesson
Vid *CENC 987 Kbps | 1280x720 | Main
Aud *CENC 135 Kbps | 2CH
[Download progress...]
✅ Download Complete!

# [3] DECRYPTION
🔓 Decrypting files with mp4decrypt...
✅ Video decrypted (720p)
✅ Audio decrypted

# [4] MERGE
🔧 Merging decrypted audio and video...
✅ Final file created!

📁 READY TO PLAY: downloads/physics_lesson_720p_FINAL.mp4
   Resolution: 1280x720
```

---

## 🔬 Why Widevine L3 Can Be Bypassed

### **Security Levels**
- **L1** - Hardware-backed (TEE/TrustZone) - **Secure**
- **L2** - Hybrid (some hardware) - **Moderately secure**
- **L3** - Software-only - **Vulnerable** ⚠️

### **L3 Vulnerability**
1. **Keys in memory** - Not in secure hardware
2. **Software CDM** - Can be emulated/reversed
3. **Device credentials extractable** - From rooted Android
4. **No hardware attestation** - Server can't verify real device

### **Attack Chain**
```
Rooted Android → Extract WVD → pywidevine → License Server
                                    ↓
                            Thinks it's real device
                                    ↓
                            Returns decryption keys
```

**This is why L3 is considered broken for high-value content.**

---

## ⚠️ Legal & Ethical Notice

**Educational Purpose Only**

This tool demonstrates:
- Widevine L3 security limitations
- CDM protocol implementation
- DRM bypass techniques (for research)

**Important:**
- ⚠️ Bypassing DRM may violate Terms of Service
- ⚠️ May be illegal under DMCA (US) or similar laws
- ✅ Use only on content you have legal rights to access
- ✅ For educational/research purposes only

**We are not responsible for misuse.**

---

## 🎓 Learning Resources

- [Widevine L3 Research](https://neodyme.io/en/blog/widevine_l3) - Original security research
- [pywidevine](https://github.com/devine-dl/pywidevine) - Python CDM library
- [Widevine Architecture](https://developers.google.com/widevine) - Official docs
- [CENC Standard](https://www.w3.org/TR/encrypted-media/) - Common Encryption spec

---

## 🙏 Credits

- **Neodyme Labs** - Widevine L3 Playground research
- **pywidevine** - CDM implementation
- **N_m3u8DL-RE** - Stream downloader
- **Bento4** - mp4decrypt tool
- **FFmpeg** - Multimedia framework

---

## 📊 Technical Specifications

**Output Quality:**
- Resolution: 1280x720 (HD)
- Video: H264, 24fps, ~1000 kbps
- Audio: AAC, 48kHz, Stereo, ~135 kbps
- Container: MP4

**Performance:**
- Key extraction: ~2 seconds
- Download: Depends on file size (~5-10 minutes for 1 hour video)
- Decryption: ~10 seconds
- Merge: ~5 seconds

**Requirements:**
- Python 3.8+
- pywidevine, requests
- N_m3u8DL-RE, mp4decrypt, ffmpeg
- Valid WVD file

---

**Version:** 1.0  
**Status:** ✅ Production Ready  
**Last Updated:** 2026-02-09

---

**One script. One purpose. Clean and simple.** 🚀
