import subprocess
import requests
from pathlib import Path
from xml.etree import ElementTree as ET
import sys
import re

try:
    from pywidevine.cdm import Cdm
    from pywidevine.device import Device
    from pywidevine.pssh import PSSH
    PYWIDEVINE_AVAILABLE = True
except ImportError:
    PYWIDEVINE_AVAILABLE = False


def extract_metadata_from_mpd(mpd_url):
    """Extract metadata (title, duration) from MPD manifest"""
    headers = {
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    response = requests.get(mpd_url, headers=headers, timeout=10)
    response.raise_for_status()
    
    root = ET.fromstring(response.content)
    
    metadata = {
        'title': None,
        'duration': None
    }
    
    # Try to extract title from URL (content ID)
    # URL format: .../contentid/hash/hash.mpd
    parts = mpd_url.rstrip('/').split('/')
    if len(parts) >= 3:
        content_id = parts[-2]  # Get the hash before .mpd
        metadata['title'] = content_id[:16]  # Use first 16 chars as title
    
    # Try to get duration from MPD
    for elem in root.iter():
        if 'mediaPresentationDuration' in elem.attrib:
            duration_str = elem.attrib['mediaPresentationDuration']
            # Parse ISO 8601 duration (PT1H2M3S format)
            match = re.search(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?', duration_str)
            if match:
                hours = int(match.group(1) or 0)
                minutes = int(match.group(2) or 0)
                seconds = float(match.group(3) or 0)
                total_minutes = hours * 60 + minutes + seconds / 60
                metadata['duration'] = f"{int(total_minutes)}min"
    
    return metadata


def extract_pssh_from_mpd(mpd_url):
    """Extract PSSH box from MPD manifest"""
    print(f"📥 Fetching MPD...")
    
    headers = {
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    response = requests.get(mpd_url, headers=headers, timeout=10)
    response.raise_for_status()
    
    root = ET.fromstring(response.content)
    
    # Look for PSSH
    for elem in root.iter():
        if 'pssh' in elem.tag.lower() or elem.tag.endswith('PSSH'):
            if elem.text:
                print(f"✅ Found PSSH")
                return elem.text.strip()
        
        if 'ContentProtection' in elem.tag:
            for child in elem:
                if 'pssh' in child.tag.lower() and child.text:
                    print(f"✅ Found PSSH in ContentProtection")
                    return child.text.strip()
    
    raise Exception("No PSSH found in MPD")


def get_keys(mpd_url, license_url, wvd_path):
    """Extract decryption keys using pywidevine"""
    if not PYWIDEVINE_AVAILABLE:
        raise Exception("pywidevine is required but not installed! Install with: uv pip install pywidevine")

    print("\n🔑 Extracting decryption keys...")
    
    # Headers for license request
    headers = {
        'accept': '*/*',
        'accept-language': 'en-IN,en;q=0.9',
        'dnt': '1',
        'origin': 'https://testbook.com',
        'referer': 'https://testbook.com/',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36'
    }
    
    # 1. Extract PSSH
    pssh_b64 = extract_pssh_from_mpd(mpd_url)
    
    # 2. Load WVD device
    print(f"📱 Loading device: {wvd_path}")
    device = Device.load(wvd_path)
    
    # 3. Create CDM
    cdm = Cdm.from_device(device)
    
    # 4. Parse PSSH
    pssh = PSSH(pssh_b64)
    
    # 5. Open session and get challenge
    session_id = cdm.open()
    print(f"🔓 CDM session opened")
    
    challenge = cdm.get_license_challenge(session_id, pssh)
    print(f"📤 Generated license challenge ({len(challenge)} bytes)")
    
    # 6. Send to license server
    print(f"🌐 Requesting license from server...")
    license_response = requests.post(
        license_url,
        data=challenge,
        headers=headers,
        timeout=15
    )
    
    if license_response.status_code != 200:
        print(f"❌ License server returned {license_response.status_code}")
        print(f"Response: {license_response.text[:200]}")
        cdm.close(session_id)
        raise Exception(f"License request failed: {license_response.text[:100]}")
    
    print(f"✅ Received license ({len(license_response.content)} bytes)")
    
    # 7. Parse license
    cdm.parse_license(session_id, license_response.content)
    
    # 8. Extract keys
    keys = []
    for key in cdm.get_keys(session_id):
        if key.type == 'CONTENT':
            # Handle both string and bytes formats
            if isinstance(key.kid, bytes):
                key_id = key.kid.hex()
            else:
                key_id = str(key.kid).replace('-', '')  # Remove dashes from UUID format
            
            if isinstance(key.key, bytes):
                key_value = key.key.hex()
            else:
                key_value = str(key.key).replace('-', '')
            
            keys.append(f"{key_id}:{key_value}")
            print(f"🔑 {key_id}:{key_value}")
    
    cdm.close(session_id)
    
    if not keys:
        raise Exception("No content keys found")
    
    # Cache keys
    cache_dir = Path("./vaults")
    cache_dir.mkdir(exist_ok=True)
    cache_file = cache_dir / "twinvine_keys_latest.txt"
    with open(cache_file, 'w') as f:
        f.write(f"# TwinVine Keys - {mpd_url}\n")
        for key in keys:
            f.write(f"{key}\n")
    print(f"💾 Keys cached to: {cache_file}")
    
    return keys


def download_with_keys(mpd_url, keys, output_name):
    """Download using N_m3u8DL-RE with extracted keys, then decrypt and merge"""
    print("\n📦 Starting download with N_m3u8DL-RE...")
    
    # Locate binary
    binary_path = "N_m3u8DL-RE"
    local_binary = Path("./bin/N_m3u8DL-RE")
    if local_binary.exists():
        binary_path = str(local_binary)
    
    # Create directories
    Path("./downloads").mkdir(exist_ok=True)
    Path("./downloads/tmp").mkdir(exist_ok=True)
    
    # Build command — explicitly select highest quality video + best audio
    cmd = [
        binary_path,
        mpd_url,
        "--save-name", output_name,
        "--save-dir", "./downloads",
        "--tmp-dir", "./downloads/tmp",
        "--binary-merge",
        "-mt",
        "--auto-select",           # Pick best audio track automatically
        "--select-video", "best",  # Explicitly pick highest resolution video
        "--thread-count", "16",    # Max download threads for speed
        "--check-segments-count", "false",  # Don't fail on segment count mismatch
    ]
    
    # Add keys
    for key in keys:
        cmd.extend(["--key", key])
    
    # Add headers
    cmd.extend([
        "-H", "accept: */*",
        "-H", "origin: https://testbook.com",
        "-H", "referer: https://testbook.com/",
        "-H", "user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
    ])
    
    print(f"🚀 Downloading BEST quality video to: ./downloads/{output_name}")
    print("=" * 80)
    
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print("\n" + "=" * 80)
        print("✅ Download Complete!")
        
        # Check if we have separate audio and video files
        video_file = Path(f"./downloads/{output_name}.mp4")
        audio_file = Path(f"./downloads/{output_name}.m4a")
        
        if video_file.exists() and audio_file.exists():
            # Step 1: Decrypt the files using mp4decrypt
            print("\n🔓 Decrypting files with mp4decrypt...")
            
            video_decrypted = Path(f"./downloads/{output_name}_decrypted.mp4")
            audio_decrypted = Path(f"./downloads/{output_name}_decrypted.m4a")
            
            # Build mp4decrypt command with all keys
            decrypt_args = []
            for key in keys:
                decrypt_args.extend(["--key", key])
            
            # Decrypt video
            decrypt_video_cmd = ["mp4decrypt"] + decrypt_args + [str(video_file), str(video_decrypted)]
            decrypt_result = subprocess.run(decrypt_video_cmd, capture_output=True, text=True)
            
            if decrypt_result.returncode != 0:
                print(f"⚠️  Video decryption warning: {decrypt_result.stderr[:200]}")
            else:
                print(f"✅ Video decrypted (720p)")
            
            # Decrypt audio
            decrypt_audio_cmd = ["mp4decrypt"] + decrypt_args + [str(audio_file), str(audio_decrypted)]
            decrypt_result = subprocess.run(decrypt_audio_cmd, capture_output=True, text=True)
            
            if decrypt_result.returncode != 0:
                print(f"⚠️  Audio decryption warning: {decrypt_result.stderr[:200]}")
            else:
                print(f"✅ Audio decrypted")
            
            # Step 2: Merge decrypted files — detect actual resolution for naming
            if video_decrypted.exists() and audio_decrypted.exists():
                # Detect actual resolution with ffprobe
                res_label = "FINAL"
                try:
                    probe = subprocess.run(
                        ["ffprobe", "-v", "error", "-select_streams", "v:0",
                         "-show_entries", "stream=width,height",
                         "-of", "csv=p=0", str(video_decrypted)],
                        capture_output=True, text=True
                    )
                    if probe.returncode == 0 and probe.stdout.strip():
                        w, h = probe.stdout.strip().split(",")
                        res_label = f"{h}p"  # e.g. 720p, 1080p, 2160p
                        print(f"📐 Detected resolution: {w}x{h} ({res_label})")
                except Exception:
                    pass

                merged_file = Path(f"./downloads/{output_name}_{res_label}_FINAL.mp4")
                print("\n🔧 Merging decrypted audio and video...")
                merge_cmd = [
                    "ffmpeg",
                    "-i", str(video_decrypted),
                    "-i", str(audio_decrypted),
                    "-c", "copy",
                    "-map", "0:v:0",
                    "-map", "1:a:0",
                    str(merged_file),
                    "-y"
                ]
                
                merge_result = subprocess.run(merge_cmd, capture_output=True, text=True)
                
                if merge_result.returncode == 0:
                    print(f"✅ Final {res_label} file created!")
                    print(f"\n📁 READY TO PLAY: {merged_file}")
                    
                    video_file.unlink(missing_ok=True)
                    audio_file.unlink(missing_ok=True)
                    video_decrypted.unlink(missing_ok=True)
                    audio_decrypted.unlink(missing_ok=True)
                    print("🗑️  Cleaned up intermediate files")
                else:
                    print(f"⚠️  Merge failed. Decrypted files available:")
                    print(f"   Video: {video_decrypted}")
                    print(f"   Audio: {audio_decrypted}")
            else:
                print(f"⚠️  Decryption may have failed. Check files manually.")
        else:
            print(f"📁 File: ./downloads/{output_name}.*")
        
        print("=" * 80)
        return True
    else:
        print("\n" + "=" * 80)
        print(f"❌ Download failed (exit code {result.returncode})")
        print("=" * 80)
        return False
