#!/usr/bin/env python3
"""
TwinVine - Complete DRM Video Downloader
All-in-one solution for downloading DRM-protected courses

Usage:
  python twinvine.py server      # Start auto-capture server
  python twinvine.py status      # Show queue status
  python twinvine.py download    # Download all videos
  python twinvine.py clear       # Clear queue
  python twinvine.py single      # Download single video (manual)
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

# Try to import Flask for server mode
try:
    from flask import Flask, request, jsonify
    from flask_cors import CORS
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

# Import core functions
from twinvine_720p import get_keys, extract_metadata_from_mpd, download_with_keys


class TwinVine:
    """Complete TwinVine downloader"""
    
    def __init__(self, max_workers=3):
        self.cache_dir = Path("./vaults/course_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.queue_file = self.cache_dir / "auto_queue.json"
        self.max_workers = max_workers
        self.lock = threading.Lock()
    
    # ==================== QUEUE MANAGEMENT ====================
    
    def load_queue(self):
        """Load queue from file"""
        if not self.queue_file.exists():
            return []
        try:
            with open(self.queue_file, 'r') as f:
                return json.load(f)
        except:
            return []
    
    def save_queue(self, queue):
        """Save queue to file (thread-safe)"""
        with self.lock:
            with open(self.queue_file, 'w') as f:
                json.dump(queue, f, indent=2)
    
    def remove_duplicates(self):
        """Remove duplicate entries from queue"""
        queue = self.load_queue()
        seen = set()
        unique = []
        
        for item in queue:
            if item['mpd_url'] not in seen:
                seen.add(item['mpd_url'])
                unique.append(item)
        
        # Renumber
        for i, item in enumerate(unique):
            item['number'] = i + 1
            # Keep original filename if it has a proper name
            if not item['filename'].startswith('lesson'):
                continue
            title = item['metadata'].get('title', f'lesson{i+1:02d}')[:20]
            item['filename'] = f"lesson{i+1:02d}_{title}"
        
        self.save_queue(unique)
        return len(queue) - len(unique)
    
    # ==================== STATUS & INFO ====================
    
    def show_status(self):
        """Show queue status"""
        queue = self.load_queue()
        
        if not queue:
            print("\n📋 Queue is empty")
            print("\nTo auto-capture:")
            print("1. Start server: python twinvine.py server")
            print("2. Open browser extension")
            print("3. Play each video briefly (10 sec)")
            print("4. Extension auto-captures and extracts keys")
            print("5. Run: python twinvine.py download")
            return
        
        print(f"\n📚 Auto-Captured Queue ({len(queue)} lessons)")
        print("="*80)
        
        for lesson in queue:
            status = lesson.get('status', 'pending')
            icon = '✅' if status == 'downloaded' else '⏳' if status == 'pending' else '❌'
            duration = lesson.get('metadata', {}).get('duration', '?')
            filename = lesson.get('filename', f"lesson{lesson['number']:02d}")
            
            print(f"{icon} Lesson {lesson['number']:02d}: {filename} ({duration})")
        
        pending = len([l for l in queue if l.get('status') == 'pending'])
        downloaded = len([l for l in queue if l.get('status') == 'downloaded'])
        
        print("="*80)
        print(f"✅ Downloaded: {downloaded}")
        print(f"⏳ Pending: {pending}")
        
        if pending > 0:
            print(f"\nReady to download! Run: python twinvine.py download")
    
    # ==================== DOWNLOAD ====================
    
    def download_single_lesson(self, lesson, queue):
        """Download a single lesson (runs in thread)"""
        lesson_num = lesson['number']
        filename = lesson['filename']
        
        try:
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
                lesson['status'] = 'failed'
                self.save_queue(queue)
                return False
            
            # Decrypt and merge
            video_file = Path(f"./downloads/{filename}.mp4")
            audio_file = Path(f"./downloads/{filename}.m4a")
            
            if video_file.exists() and audio_file.exists():
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
                    
                    lesson['status'] = 'downloaded'
                    lesson['downloaded_at'] = datetime.now().isoformat()
                    self.save_queue(queue)
                    return True
            
            return False
            
        except Exception as e:
            lesson['status'] = 'failed'
            self.save_queue(queue)
            return False
    
    def download_all(self):
        """Download all lessons in parallel"""
        # Remove duplicates first
        removed = self.remove_duplicates()
        if removed > 0:
            print(f"✅ Removed {removed} duplicate(s)")
        
        queue = self.load_queue()
        
        if not queue:
            print("❌ Queue is empty!")
            print("\nStart server first: python twinvine.py server")
            return
        
        pending = [l for l in queue if l.get('status') == 'pending']
        
        if not pending:
            print("✅ All lessons already downloaded!")
            return
        
        print("="*80)
        print("🚀 PARALLEL DOWNLOAD MODE")
        print("="*80)
        print()
        print(f"📋 {len(pending)} lessons ready to download")
        print(f"⚡ Will download {self.max_workers} videos simultaneously")
        print()
        
        for lesson in pending[:5]:
            print(f"  • {lesson['filename']} ({lesson.get('metadata', {}).get('duration', '?')})")
        
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
        
        # Download in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_lesson = {
                executor.submit(self.download_single_lesson, lesson, queue): lesson 
                for lesson in pending
            }
            
            for future in as_completed(future_to_lesson):
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
        print(f"🎉 Download Complete!")
        print(f"✅ Downloaded: {downloaded}/{len(pending)}")
        if failed > 0:
            print(f"❌ Failed: {failed}")
        print(f"⏱️  Total time: {int(elapsed/60)}m {int(elapsed%60)}s")
        if len(pending) > 0:
            print(f"⚡ Average: {int(elapsed/len(pending))}s per video")
        print("="*80)
    
    # ==================== SERVER MODE ====================
    
    def start_server(self):
        """Start auto-capture server"""
        if not FLASK_AVAILABLE:
            print("❌ Flask not installed!")
            print("\nInstall: uv pip install flask flask-cors")
            return
        
        app = Flask(__name__)
        CORS(app)
        
        @app.route('/extract-keys', methods=['POST'])
        def extract_keys():
            """Extract keys from MPD and License URLs"""
            try:
                data = request.json
                mpd_url = data.get('mpd_url')
                license_url = data.get('license_url')
                page_title = data.get('page_title', '')  # Get page title from extension
                
                if not mpd_url or not license_url:
                    return jsonify({'error': 'Missing URLs'}), 400
                
                # Load queue to check for duplicates
                queue = self.load_queue()
                
                # Check if this MPD URL already exists
                for lesson in queue:
                    if lesson.get('mpd_url') == mpd_url:
                        return jsonify({
                            'success': False,
                            'error': 'duplicate',
                            'message': 'This video is already in the queue',
                            'existing_lesson': lesson.get('filename'),
                            'queue_length': len(queue)
                        }), 200
                
                print(f"\n{'='*80}")
                print(f"🔑 Auto-extracting keys...")
                print(f"{'='*80}")
                
                # Extract metadata
                print("📊 Extracting metadata...")
                try:
                    metadata = extract_metadata_from_mpd(mpd_url)
                    print(f"📝 Title: {metadata.get('title', 'unknown')}")
                    print(f"⏱️  Duration: {metadata.get('duration', 'unknown')}")
                except Exception as e:
                    print(f"⚠️  Metadata extraction failed: {e}")
                    metadata = {'title': None, 'duration': None}
                
                # Extract keys
                print("🔑 Extracting keys...")
                wvd_path = "./WVDs/device.wvd"
                
                try:
                    keys = get_keys(mpd_url, license_url, wvd_path)
                except Exception as e:
                    error_msg = str(e)
                    
                    if 'expired' in error_msg.lower() or '403' in error_msg:
                        print("❌ Token expired!")
                        return jsonify({
                            'success': False,
                            'error': 'token_expired',
                            'message': 'License token has expired. Please refresh the page and play the video again.',
                            'queue_length': len(queue)
                        }), 200
                    
                    print(f"❌ Key extraction failed: {error_msg}")
                    return jsonify({
                        'success': False,
                        'error': 'extraction_failed',
                        'message': f'Key extraction failed: {error_msg}',
                        'queue_length': len(queue)
                    }), 500
                
                if not keys:
                    return jsonify({
                        'success': False,
                        'error': 'no_keys',
                        'message': 'No keys were extracted',
                        'queue_length': len(queue)
                    }), 500
                
                print(f"✅ Extracted {len(keys)} keys")
                
                # Generate filename from page title or metadata
                lesson_num = len(queue) + 1
                
                if page_title:
                    # Clean page title for filename
                    filename = page_title.strip()
                    # Remove common suffixes
                    filename = filename.replace(' - Testbook', '').replace(' | Testbook', '')
                    # Clean invalid characters
                    filename = filename.replace('/', '_').replace('\\', '_').replace(':', '_').replace('?', '_').replace('*', '_').replace('|', '_')
                    filename = f"lesson{lesson_num:02d}_{filename[:50]}"
                else:
                    title = metadata.get('title', f'lesson{lesson_num:02d}')
                    filename = f"lesson{lesson_num:02d}_{title[:20]}"
                    filename = filename.replace('/', '_').replace('\\', '_').replace(':', '_').replace('?', '_').replace('*', '_')
                
                # Add to queue
                lesson = {
                    'number': lesson_num,
                    'filename': filename,
                    'mpd_url': mpd_url,
                    'keys': keys,
                    'metadata': metadata,
                    'page_title': page_title,
                    'captured_at': datetime.now().isoformat(),
                    'status': 'pending'
                }
                
                queue.append(lesson)
                self.save_queue(queue)
                
                print(f"✅ Added to queue: {filename}")
                print(f"📋 Queue now has {len(queue)} lessons")
                print(f"{'='*80}\n")
                
                return jsonify({
                    'success': True,
                    'keys': keys,
                    'metadata': metadata,
                    'filename': filename,
                    'lesson_number': lesson_num,
                    'queue_length': len(queue)
                })
                
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({
                    'success': False,
                    'error': 'server_error',
                    'message': str(e)
                }), 500
        
        @app.route('/queue', methods=['GET'])
        def get_queue():
            """Get current queue"""
            queue = self.load_queue()
            return jsonify({
                'queue': queue,
                'total': len(queue),
                'pending': len([l for l in queue if l.get('status') == 'pending']),
                'downloaded': len([l for l in queue if l.get('status') == 'downloaded'])
            })
        
        @app.route('/health', methods=['GET'])
        def health():
            """Health check"""
            return jsonify({'status': 'running', 'queue_length': len(self.load_queue())})
        
        print("="*80)
        print("🎬 TwinVine Auto-Capture Server")
        print("="*80)
        print()
        print("Server running on http://localhost:8765")
        print()
        print("How to use:")
        print("1. Keep this server running")
        print("2. Open browser extension")
        print("3. Play videos in browser")
        print("4. Extension automatically sends URLs here")
        print("5. Keys extracted and cached automatically")
        print("6. Later: python twinvine.py download")
        print()
        print("="*80)
        print()
        
        app.run(host='localhost', port=8765, debug=False)
    
    # ==================== SINGLE VIDEO MODE ====================
    
    def download_single(self):
        """Download single video (manual mode)"""
        from twinvine_720p import main as single_main
        single_main()
    
    # ==================== CLEAR ====================
    
    def clear_queue(self):
        """Clear queue"""
        confirm = input("⚠️  Clear entire queue? (y/N): ").strip().lower()
        if confirm == 'y':
            self.save_queue([])
            print("✅ Queue cleared")


def main():
    if len(sys.argv) < 2:
        print("="*80)
        print("🎬 TwinVine - Complete DRM Video Downloader")
        print("="*80)
        print()
        print("Commands:")
        print("  python twinvine.py server      # Start auto-capture server")
        print("  python twinvine.py status      # Show queue status")
        print("  python twinvine.py download    # Download all videos")
        print("  python twinvine.py single      # Download single video")
        print("  python twinvine.py clear       # Clear queue")
        print()
        print("Options:")
        print("  --workers N    Parallel downloads (default: 3)")
        print()
        print("Examples:")
        print("  python twinvine.py server")
        print("  python twinvine.py download --workers 5")
        print()
        print("="*80)
        return
    
    command = sys.argv[1].lower()
    
    # Parse workers
    max_workers = 3
    if '--workers' in sys.argv:
        try:
            idx = sys.argv.index('--workers')
            max_workers = int(sys.argv[idx + 1])
        except:
            pass
    
    app = TwinVine(max_workers=max_workers)
    
    if command == 'server':
        app.start_server()
    elif command == 'status':
        app.show_status()
    elif command == 'download':
        app.download_all()
    elif command == 'single':
        app.download_single()
    elif command == 'clear':
        app.clear_queue()
    else:
        print(f"❌ Unknown command: {command}")
        print("Use: server, status, download, single, or clear")


if __name__ == "__main__":
    main()
