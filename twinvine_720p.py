#!/usr/bin/env python3
"""
Interactive TwinVine downloader - prompts for BOTH MPD and License URL
Ensures 720p quality selection

Usage:
1. Open the lesson in your browser
2. Open DevTools (F12) → Network tab
3. Play the video
4. Find the MPD URL (ends with .mpd)
5. Find the license URL (drm-server/getlicense?token=...)
6. Run this script and provide both URLs
"""
# Extract meta data and use the title of the video as the name of the file 
import subprocess
import sys
import requests
from pathlib import Path
from xml.etree import ElementTree as ET

# Try to import pywidevine
try:
    from pywidevine.cdm import Cdm
    from pywidevine.device import Device
    from pywidevine.pssh import PSSH
    PYWIDEVINE_AVAILABLE = True
except ImportError:
    print("❌ pywidevine is required but not installed!")
    print("Install with: uv pip install pywidevine")
    sys.exit(1)


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
            import re
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


def process_downloaded_files(output_name, keys, video_file, audio_file):
    """Process already downloaded encrypted files - decrypt and merge"""
    if not video_file.exists() or not audio_file.exists():
        print(f"❌ Missing files for processing:")
        if not video_file.exists():
            print(f"   Missing: {video_file}")
        if not audio_file.exists():
            print(f"   Missing: {audio_file}")
        return False
    
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
        print(f"❌ Video decryption failed: {decrypt_result.stderr[:200]}")
        return False
    else:
        print(f"✅ Video decrypted (720p)")
    
    # Decrypt audio
    decrypt_audio_cmd = ["mp4decrypt"] + decrypt_args + [str(audio_file), str(audio_decrypted)]
    decrypt_result = subprocess.run(decrypt_audio_cmd, capture_output=True, text=True)
    
    if decrypt_result.returncode != 0:
        print(f"❌ Audio decryption failed: {decrypt_result.stderr[:200]}")
        return False
    else:
        print(f"✅ Audio decrypted")
    
    # Merge decrypted files
    merged_file = Path(f"./downloads/{output_name}_720p_FINAL.mp4")
    
    if video_decrypted.exists() and audio_decrypted.exists():
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
            print(f"✅ Final 720p file created!")
            print(f"\n📁 READY TO PLAY: {merged_file}")
            print(f"   Resolution: 1280x720")
            
            # Cleanup
            video_file.unlink(missing_ok=True)
            audio_file.unlink(missing_ok=True)
            video_decrypted.unlink(missing_ok=True)
            audio_decrypted.unlink(missing_ok=True)
            print("🗑️  Cleaned up intermediate files")
            return True
        else:
            print(f"❌ Merge failed: {merge_result.stderr[:200]}")
            print(f"   Decrypted files available:")
            print(f"   Video: {video_decrypted}")
            print(f"   Audio: {audio_decrypted}")
            return False
    else:
        print(f"❌ Decryption failed. Missing decrypted files.")
        return False


def download_with_keys(mpd_url, keys, output_name, max_retries=3):
    """Download using N_m3u8DL-RE with extracted keys, then decrypt and merge"""
    print("\n📦 Starting download with N_m3u8DL-RE...")
    
    # Check if final file already exists
    final_file = Path(f"./downloads/{output_name}_720p_FINAL.mp4")
    if final_file.exists():
        file_size_mb = final_file.stat().st_size / (1024 * 1024)
        print(f"\n⚠️  Final file already exists: {final_file}")
        print(f"   Size: {file_size_mb:.2f} MB")
        
        choice = input("\nWhat would you like to do?\n  [s] Skip (use existing file)\n  [o] Overwrite (download again)\n  [r] Rename (download with new name)\nChoice (s/o/r): ").strip().lower()
        
        if choice == 's':
            print(f"✅ Using existing file: {final_file}")
            return True
        elif choice == 'r':
            new_name = input("Enter new output name: ").strip()
            if new_name:
                output_name = new_name
                final_file = Path(f"./downloads/{output_name}_720p_FINAL.mp4")
                print(f"📝 Will save as: {output_name}")
            else:
                print("❌ Invalid name, aborting")
                return False
        elif choice == 'o':
            print("🔄 Will overwrite existing file")
        else:
            print("❌ Invalid choice, aborting")
            return False
    
    # Check for partial downloads (encrypted files without final)
    video_file = Path(f"./downloads/{output_name}.mp4")
    audio_file = Path(f"./downloads/{output_name}.m4a")
    
    if video_file.exists() or audio_file.exists():
        print(f"\n⚠️  Found partial download:")
        if video_file.exists():
            print(f"   Video: {video_file} ({video_file.stat().st_size / (1024*1024):.2f} MB)")
        if audio_file.exists():
            print(f"   Audio: {audio_file} ({audio_file.stat().st_size / (1024*1024):.2f} MB)")
        
        resume = input("\nResume from partial download? (y/N): ").strip().lower()
        if resume == 'y':
            print("🔄 Attempting to resume (will skip download, go straight to decrypt/merge)")
            # Skip to decryption/merge step
            return process_downloaded_files(output_name, keys, video_file, audio_file)
        else:
            print("🗑️  Will clean up partial files and start fresh")
            video_file.unlink(missing_ok=True)
            audio_file.unlink(missing_ok=True)
    
    # Locate binary
    binary_path = "N_m3u8DL-RE"
    local_binary = Path("./bin/N_m3u8DL-RE")
    if local_binary.exists():
        binary_path = str(local_binary)
    
    # Create directories
    Path("./downloads").mkdir(exist_ok=True)
    Path("./downloads/tmp").mkdir(exist_ok=True)
    
    # Thread configurations to try (start with more threads, reduce on failure)
    thread_configs = [
        {"threads": 16, "name": "16 threads (fast)"},
        {"threads": 8, "name": "8 threads (balanced)"},
        {"threads": 4, "name": "4 threads (stable)"},
        {"threads": 1, "name": "1 thread (safe)"}
    ]
    
    result = None
    
    for attempt in range(max_retries):
        # Use different thread count for each retry
        config = thread_configs[min(attempt, len(thread_configs) - 1)]
        thread_count = config["threads"]
        
        print(f"\n{'🔄 Retry ' + str(attempt + 1) if attempt > 0 else '🚀 Attempt 1'} - Using {config['name']}")
        
        # Build command - select 720p video (highest quality) and audio
        cmd = [
            binary_path,
            mpd_url,
            "--save-name", output_name,
            "--save-dir", "./downloads",
            "--tmp-dir", "./downloads/tmp",
            "--binary-merge",
            "--thread-count", str(thread_count),  # Configurable thread count
            "--auto-select",  # Automatically select best video and audio
            "--check-segments-count", "false"  # Skip segment count check (helps with failures)
        ]
        
        # Add keys
        for key in keys:
            cmd.extend(["--key", key])
        
        # Add headers
        cmd.extend([
            "-H", "accept: */*",
            "-H", "origin: https://example.com",
            "-H", "referer: https://example.com/",
            "-H", "user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
        ])
        
        print(f"📥 Downloading 720p video to: ./downloads/{output_name}")
        print("=" * 80)
        
        result = subprocess.run(cmd)
        
        if result.returncode == 0:
            print("\n" + "=" * 80)
            print("✅ Download Complete!")
            break
        else:
            print(f"\n⚠️  Download failed with exit code {result.returncode}")
            if attempt < max_retries - 1:
                print(f"🔄 Retrying with fewer threads...")
                # Clean up partial downloads
                import shutil
                tmp_dir = Path(f"./downloads/tmp/{output_name}")
                if tmp_dir.exists():
                    shutil.rmtree(tmp_dir)
                    print(f"🗑️  Cleaned up partial download")
            else:
                print(f"❌ All {max_retries} attempts failed")
    
    if result and result.returncode == 0:
        # Check if we have separate audio and video files
        video_file = Path(f"./downloads/{output_name}.mp4")
        audio_file = Path(f"./downloads/{output_name}.m4a")
        
        if video_file.exists() and audio_file.exists():
            # Use the helper function to decrypt and merge
            success = process_downloaded_files(output_name, keys, video_file, audio_file)
            print("=" * 80)
            return success
        else:
            print(f"📁 File: ./downloads/{output_name}.*")
        
        print("=" * 80)
        return True
    else:
        print("\n" + "=" * 80)
        if result:
            print(f"❌ Download failed (exit code {result.returncode})")
        else:
            print(f"❌ Download failed")
        print("=" * 80)
        return False



def main():
    print("=" * 80)
    print("🎬 TwinVine 720p Downloader")
    print("=" * 80)
    print()
    print("INSTRUCTIONS:")
    print("1. Open the lesson you want to download")
    print("2. Open DevTools (F12) → Network tab")
    print("3. Play the video")
    print("4. Find TWO URLs in the Network tab:")
    print("   a) MPD URL (ends with .mpd)")
    print("   b) License URL (drm-server/getlicense?token=...)")
    print()
    print("=" * 80)
    print()
    
    # Configuration
    wvd_path = "./WVDs/device.wvd"
    
    # Batch download mode
    videos_downloaded = 0
    
    while True:
        if videos_downloaded > 0:
            print("\n" + "=" * 80)
            print(f"✅ Downloaded {videos_downloaded} video(s) so far")
            print("=" * 80)
            print()
        
        # Get MPD URL
        mpd_url = input("📍 Paste the MPD URL (.mpd): ").strip()
        
        if not mpd_url:
            if videos_downloaded > 0:
                print(f"\n🎉 Batch download complete! Downloaded {videos_downloaded} video(s)")
                break
            else:
                print("❌ No MPD URL provided!")
                sys.exit(1)
        
        if not mpd_url.endswith('.mpd'):
            print("⚠️  Warning: URL doesn't end with .mpd - are you sure this is correct?")
        
        print()
        
        # Get License URL
        license_url = input("🔐 Paste the License URL (with token): ").strip()
        
        if not license_url:
            print("❌ No license URL provided!")
            if videos_downloaded > 0:
                print(f"Stopping batch download. Downloaded {videos_downloaded} video(s)")
                break
            sys.exit(1)
        
        if "getlicense" not in license_url:
            print("❌ Invalid license URL! Must contain 'getlicense'")
            continue
        
        if "token=" not in license_url:
            print("❌ License URL must contain a token parameter!")
            continue
        
        print()
        
        try:
            # Extract metadata from MPD
            print("📊 Extracting metadata...")
            metadata = extract_metadata_from_mpd(mpd_url)
            
            # Use title from metadata or ask user
            if metadata['title']:
                suggested_name = metadata['title'].replace('/', '_').replace(' ', '_')
                print(f"📝 Detected title: {metadata['title']}")
                if metadata['duration']:
                    print(f"⏱️  Duration: {metadata['duration']}")
                print()
                print(f"💡 Suggested filename: {suggested_name}")
                print("   (Press Enter to use suggested name, or type a custom name)")
                print()
                
                while True:
                    custom_name = input(f"Filename: ").strip()
                    
                    # If empty, use suggested name
                    if not custom_name:
                        output_name = suggested_name
                        break
                    
                    # Validate: reject if looks like a URL
                    if custom_name.startswith('http://') or custom_name.startswith('https://'):
                        print("❌ That looks like a URL! Please enter just the filename.")
                        print(f"   Example: lesson1, ancient_history, etc.")
                        continue
                    
                    # Validate: reject if too long
                    if len(custom_name) > 100:
                        print("❌ Filename too long! Please use a shorter name.")
                        continue
                    
                    output_name = custom_name
                    break
            else:
                output_name = input("Enter output filename (default: twinvine_720p): ").strip() or "twinvine_720p"
            
            # Sanitize filename (remove invalid characters)
            output_name = output_name.replace('/', '_').replace('\\', '_').replace(':', '_').replace('?', '_').replace('*', '_')
            
            print()
            print("=" * 80)
            
            # Step 1: Extract keys
            keys = get_keys(mpd_url, license_url, wvd_path)
            
            # Step 2: Download with keys (720p)
            success = download_with_keys(mpd_url, keys, output_name)
            
            if success:
                videos_downloaded += 1
                
                # Ask if user wants to download another
                print()
                another = input("📥 Download another video? (y/N): ").strip().lower()
                if another != 'y':
                    print(f"\n🎉 Complete! Downloaded {videos_downloaded} video(s)")
                    break
            else:
                print("\n⚠️  Download failed. Try again or exit.")
                retry = input("Retry this video? (y/N): ").strip().lower()
                if retry != 'y':
                    if videos_downloaded > 0:
                        print(f"\nDownloaded {videos_downloaded} video(s) before error")
                    sys.exit(1)
                
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            if videos_downloaded > 0:
                print(f"Downloaded {videos_downloaded} video(s) before interruption")
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            
            if videos_downloaded > 0:
                cont = input("\nContinue with next video? (y/N): ").strip().lower()
                if cont != 'y':
                    print(f"Downloaded {videos_downloaded} video(s) before error")
                    sys.exit(1)
            else:
                sys.exit(1)


if __name__ == "__main__":
    main()

