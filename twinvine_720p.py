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
import sys
from twinvine_core import extract_metadata_from_mpd, get_keys, download_with_keys


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

