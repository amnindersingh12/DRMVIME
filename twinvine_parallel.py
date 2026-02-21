#!/usr/bin/env python3
"""
TwinVine Parallel Course Downloader
Downloads multiple videos simultaneously for maximum speed

Features:
- Parallel downloads (3-5 videos at once)
- Maximum bandwidth utilization
- Progress tracking for all downloads
- Smart key caching (extract keys first, download later)

Usage:
  python twinvine_parallel.py capture    # Capture keys from all lessons
  python twinvine_parallel.py download   # Download all in parallel
"""

import subprocess
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from tqdm import tqdm

# Import core functions
from twinvine_core import get_keys, extract_metadata_from_mpd


class ParallelDownloader:
    def __init__(self, max_workers=3):
        self.cache_dir = Path("./vaults/course_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "lessons.json"
        self.max_workers = max_workers  # Number of simultaneous downloads
        self.lock = threading.Lock()
        
    def load_cache(self):
        """Load cached lesson data"""
        if not self.cache_file.exists():
            return []
        
        try:
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        except:
            return []
    
    def save_cache(self, lessons):
        """Save lesson data to cache (thread-safe)"""
        with self.lock:
            with open(self.cache_file, 'w') as f:
                json.dump(lessons, f, indent=2)
    
    def capture_lesson(self, lesson_number):
        """Capture keys for a single lesson"""
        print(f"\n{'='*80}")
        print(f"🎯 Capturing Lesson {lesson_number}")
        print(f"{'='*80}")
        print()
        
        # Get URLs
        mpd_url = input("📍 Paste MPD URL: ").strip()
        if not mpd_url:
            return None
        
        license_url = input("🔐 Paste License URL: ").strip()
        if not license_url:
            return None
        
        print()
        
        try:
            # Extract metadata
            print("📊 Extracting metadata...")
            metadata = extract_metadata_from_mpd(mpd_url)
            
            title = metadata.get('title', f'lesson{lesson_number:02d}')
            duration = metadata.get('duration', 'unknown')
            
            print(f"📝 Title: {title}")
            print(f"⏱️  Duration: {duration}")
            
            # Extract keys NOW
            print("\n🔑 Extracting keys...")
            wvd_path = "./WVDs/device.wvd"
            keys = get_keys(mpd_url, license_url, wvd_path)
            
            if not keys:
                print("❌ Failed to extract keys")
                return None
            
            print(f"✅ Extracted {len(keys)} keys")
            
            # Get filename
            suggested_name = f"lesson{lesson_number:02d}_{title[:20]}"
            suggested_name = suggested_name.replace('/', '_').replace('\\', '_').replace(':', '_')
            
            print(f"\n💡 Suggested filename: {suggested_name}")
            print("   (Press Enter to use suggested name, or type a custom name)")
            print()
            
            while True:
                custom_name = input("Filename: ").strip()
                
                if not custom_name:
                    filename = suggested_name
                    break
                
                if custom_name.startswith('http'):
                    print("❌ That's a URL! Please enter just the filename.")
                    continue
                
                filename = custom_name.replace('/', '_').replace('\\', '_').replace(':', '_')
                break
            
            # Create lesson data
            lesson_data = {
                'number': lesson_number,
                'filename': filename,
                'mpd_url': mpd_url,
                'keys': keys,
                'metadata': {
                    'title': title,
                    'duration': duration
                },
                'captured_at': datetime.now().isoformat(),
                'status': 'pending'
            }
            
            print(f"\n✅ Lesson {lesson_number} captured!")
            
            return lesson_data
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            return None
    
    def capture_course(self):
        """Capture keys for entire course"""
        print("="*80)
        print("🎯 CAPTURE MODE - Extract Keys from All Lessons")
        print("="*80)
        print()
        print("Extract keys from each lesson (before tokens expire)")
        print("Then download all in parallel for maximum speed!")
        print()
        print("="*80)
        print()
        
        lessons = self.load_cache()
        lesson_number = len(lessons) + 1
        
        if lessons:
            print(f"📚 {len(lessons)} lessons already captured")
            print()
        
        while True:
            lesson_data = self.capture_lesson(lesson_number)
            
            if lesson_data:
                lessons.append(lesson_data)
                self.save_cache(lessons)
                
                print()
                another = input(f"📥 Capture another lesson? (y/N): ").strip().lower()
                if another != 'y':
                    break
                
                lesson_number += 1
            else:
                retry = input("Retry this lesson? (y/N): ").strip().lower()
                if retry != 'y':
                    break
        
        print(f"\n🎉 Capture complete! {len(lessons)} lessons ready")
        print(f"\nNext: python twinvine_parallel.py download")
    
    def download_single(self, lesson, lessons_list):
        """Download a single lesson (runs in thread)"""
        lesson_num = lesson['number']
        filename = lesson['filename']
        
        try:
            print(f"\n[Lesson {lesson_num}] 🚀 Starting download: {filename}")
            
            # Build N_m3u8DL-RE command
            binary_path = "N_m3u8DL-RE"
            local_binary = Path("./bin/N_m3u8DL-RE")
            if local_binary.exists():
                binary_path = str(local_binary)
            
            Path("./downloads").mkdir(exist_ok=True)
            Path(f"./downloads/tmp_{lesson_num}").mkdir(exist_ok=True)
            
            cmd = [
                binary_path,
                lesson['mpd_url'],
                "--save-name", filename,
                "--save-dir", "./downloads",
                "--tmp-dir", f"./downloads/tmp_{lesson_num}",
                "--binary-merge",
                "-mt",
                "--auto-select"
            ]
            
            # Add keys
            for key in lesson['keys']:
                cmd.extend(["--key", key])
            
            # Add headers
            cmd.extend([
                "-H", "accept: */*",
                "-H", "origin: https://testbook.com",
                "-H", "referer: https://testbook.com/",
                "-H", "user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            ])
            
            # Download
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"\n[Lesson {lesson_num}] ❌ Download failed")
                lesson['status'] = 'failed'
                self.save_cache(lessons_list)
                return False
            
            # Decrypt and merge
            video_file = Path(f"./downloads/{filename}.mp4")
            audio_file = Path(f"./downloads/{filename}.m4a")
            
            if video_file.exists() and audio_file.exists():
                print(f"[Lesson {lesson_num}] 🔓 Decrypting...")
                
                video_decrypted = Path(f"./downloads/{filename}_decrypted.mp4")
                audio_decrypted = Path(f"./downloads/{filename}_decrypted.m4a")
                
                # Decrypt
                decrypt_args = []
                for key in lesson['keys']:
                    decrypt_args.extend(["--key", key])
                
                subprocess.run(["mp4decrypt"] + decrypt_args + [str(video_file), str(video_decrypted)], 
                             capture_output=True)
                subprocess.run(["mp4decrypt"] + decrypt_args + [str(audio_file), str(audio_decrypted)], 
                             capture_output=True)
                
                # Merge
                print(f"[Lesson {lesson_num}] 🔧 Merging...")
                merged_file = Path(f"./downloads/{filename}_720p_FINAL.mp4")
                
                merge_cmd = [
                    "ffmpeg", "-i", str(video_decrypted), "-i", str(audio_decrypted),
                    "-c", "copy", "-map", "0:v:0", "-map", "1:a:0",
                    str(merged_file), "-y"
                ]
                
                result = subprocess.run(merge_cmd, capture_output=True)
                
                if result.returncode == 0:
                    # Cleanup
                    video_file.unlink(missing_ok=True)
                    audio_file.unlink(missing_ok=True)
                    video_decrypted.unlink(missing_ok=True)
                    audio_decrypted.unlink(missing_ok=True)
                    
                    print(f"[Lesson {lesson_num}] ✅ Complete: {merged_file.name}")
                    
                    lesson['status'] = 'downloaded'
                    lesson['downloaded_at'] = datetime.now().isoformat()
                    self.save_cache(lessons_list)
                    return True
            
            print(f"[Lesson {lesson_num}] ❌ Merge failed")
            return False
            
        except Exception as e:
            print(f"[Lesson {lesson_num}] ❌ Error: {e}")
            lesson['status'] = 'failed'
            self.save_cache(lessons_list)
            return False
    
    def download_parallel(self):
        """Download all lessons in parallel"""
        lessons = self.load_cache()
        
        if not lessons:
            print("❌ No lessons captured yet!")
            print("\nRun: python twinvine_parallel.py capture")
            return
        
        pending = [l for l in lessons if l.get('status') == 'pending']
        
        if not pending:
            print("✅ All lessons already downloaded!")
            return
        
        print("="*80)
        print("🚀 PARALLEL DOWNLOAD MODE - Maximum Speed!")
        print("="*80)
        print()
        print(f"📋 {len(pending)} lessons ready to download")
        print(f"⚡ Will download {self.max_workers} videos simultaneously")
        print()
        
        for lesson in pending[:5]:
            print(f"  • {lesson['filename']} ({lesson['metadata'].get('duration', '?')})") 
        
        if len(pending) > 5:
            print(f"  ... and {len(pending) - 5} more")
        
        print()
        confirm = input(f"Start parallel download? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Cancelled")
            return
        
        print(f"\n🚀 Starting {self.max_workers} parallel downloads...")
        print("="*80)
        print()
        
        start_time = time.time()
        downloaded = 0
        failed = 0
        
        # Create progress bar
        pbar = tqdm(
            total=len(pending),
            desc="📥 Overall Progress",
            unit="video",
            bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]',
            ncols=100
        )
        
        # Download in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all download tasks
            future_to_lesson = {
                executor.submit(self.download_single, lesson, lessons): lesson 
                for lesson in pending
            }
            
            # Process completed downloads
            for future in as_completed(future_to_lesson):
                lesson = future_to_lesson[future]
                try:
                    success = future.result()
                    if success:
                        downloaded += 1
                        pbar.set_postfix_str(f"✅ {downloaded} | ❌ {failed}")
                    else:
                        failed += 1
                        pbar.set_postfix_str(f"✅ {downloaded} | ❌ {failed}")
                except Exception as e:
                    failed += 1
                    pbar.set_postfix_str(f"✅ {downloaded} | ❌ {failed}")
                
                pbar.update(1)
        
        pbar.close()
        elapsed = time.time() - start_time
        
        # Summary
        print("\n" + "="*80)
        print(f"🎉 Parallel Download Complete!")
        print(f"✅ Downloaded: {downloaded}/{len(pending)}")
        if failed > 0:
            print(f"❌ Failed: {failed}")
        print(f"⏱️  Total time: {int(elapsed/60)}m {int(elapsed%60)}s")
        print(f"⚡ Average: {int(elapsed/len(pending))}s per video")
        print("="*80)
    
    def show_status(self):
        """Show course status"""
        lessons = self.load_cache()
        
        if not lessons:
            print("📋 No lessons captured yet")
            return
        
        print(f"\n📚 Course Status ({len(lessons)} lessons)")
        print("="*80)
        
        for lesson in lessons:
            status = lesson.get('status', 'pending')
            icon = '✅' if status == 'downloaded' else '⏳' if status == 'pending' else '❌'
            duration = lesson['metadata'].get('duration', '?')
            
            print(f"{icon} Lesson {lesson['number']:02d}: {lesson['filename']} ({duration})")
        
        pending = len([l for l in lessons if l.get('status') == 'pending'])
        downloaded = len([l for l in lessons if l.get('status') == 'downloaded'])
        
        print("="*80)
        print(f"✅ Downloaded: {downloaded}")
        print(f"⏳ Pending: {pending}")


def main():
    if len(sys.argv) < 2:
        print("="*80)
        print("🚀 TwinVine Parallel Course Downloader")
        print("="*80)
        print()
        print("Download multiple videos simultaneously for maximum speed!")
        print()
        print("Usage:")
        print("  python twinvine_parallel.py capture    # Capture keys")
        print("  python twinvine_parallel.py download   # Download in parallel")
        print("  python twinvine_parallel.py status     # Show status")
        print()
        print("Options:")
        print("  --workers N    Number of parallel downloads (default: 3)")
        print()
        print("Example:")
        print("  python twinvine_parallel.py download --workers 5")
        print()
        print("="*80)
        return
    
    command = sys.argv[1].lower()
    
    # Parse workers option
    max_workers = 3
    if '--workers' in sys.argv:
        try:
            idx = sys.argv.index('--workers')
            max_workers = int(sys.argv[idx + 1])
        except:
            pass
    
    downloader = ParallelDownloader(max_workers=max_workers)
    
    if command == 'capture':
        downloader.capture_course()
    elif command == 'download':
        downloader.download_parallel()
    elif command == 'status':
        downloader.show_status()
    else:
        print(f"❌ Unknown command: {command}")


if __name__ == "__main__":
    main()
