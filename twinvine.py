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

import os
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
from twinvine_core import get_keys, extract_metadata_from_mpd, download_with_keys

class TwinVine:
    """Complete TwinVine downloader"""
    
    def __init__(self, max_workers=3):
        self.cache_dir = Path("./vaults/course_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.queue_file = self.cache_dir / "auto_queue.json"
        self.max_workers = max_workers
        self.lock = threading.Lock()
        
        # Check dependencies in download modes
        if len(sys.argv) > 1 and sys.argv[1].lower() in ['download', 'single']:
            self._check_dependencies()
            
    def _check_dependencies(self):
        """Check if required binaries exist"""
        import shutil
        missing = []
        
        if not shutil.which("ffmpeg"):
            missing.append("ffmpeg")
            
        if not shutil.which("mp4decrypt"):
            missing.append("mp4decrypt (bento4)")
            
        if not shutil.which("N_m3u8DL-RE") and not Path("./bin/N_m3u8DL-RE").exists():
            missing.append("N_m3u8DL-RE")
            
        if missing:
            print("❌ Missing required dependencies:")
            for m in missing:
                print(f"  - {m}")
            print("\nPlease install them or place them in your system PATH (or ./bin/) before proceeding.")
            sys.exit(1)
    
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
        
        pending = len([l for l in queue if l.get('status') in ('pending', 'failed')])
        downloaded = len([l for l in queue if l.get('status') == 'downloaded'])
        failed = len([l for l in queue if l.get('status') == 'failed'])
        
        print("="*80)
        print(f"✅ Downloaded: {downloaded}")
        if failed > 0:
            print(f"❌ Failed:     {failed}  (run: python twinvine.py retry)")
        print(f"⏳ Pending:    {pending}")
        
        if pending > 0:
            print(f"\nReady to download! Run: python twinvine.py download")
    
    # ==================== DOWNLOAD ====================
    
    def _clean_tmp_dirs(self):
        """Remove leftover tmp_* directories from previous failed downloads"""
        import shutil
        tmp_dirs = list(Path("./downloads").glob("tmp_*")) if Path("./downloads").exists() else []
        for d in tmp_dirs:
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)
        if tmp_dirs:
            print(f"🗑️  Cleaned {len(tmp_dirs)} leftover tmp dir(s)")

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
            
            # Determine save dir from lesson data (3-level folder structure)
            folder = lesson.get('save_dir') or lesson.get('folder') or ''
            if folder and not str(folder).startswith('./downloads'):
                folder = f"./downloads/{folder}"
            save_dir = Path(folder) if folder else Path("./downloads")
            save_dir.mkdir(parents=True, exist_ok=True)

            tmp_dir = Path(f"./downloads/tmp_{lesson_num}")
            tmp_dir.mkdir(exist_ok=True)

            cmd = [
                binary_path,
                lesson['mpd_url'],
                "--save-name", filename,
                "--save-dir", "./downloads",     # always download flat first
                "--tmp-dir", str(tmp_dir),
                "--binary-merge",
                "-mt",
                "--auto-select",
                "--select-video", "best",         # explicitly pick highest res
                "--thread-count", "16",
                "--check-segments-count", "false",
            ]
            
            # Add keys
            for key in lesson['keys']:
                cmd.extend(["--key", key])
            
            # Add headers
            cmd.extend([
                "-H", "accept: */*",
                "-H", "origin: https://example.com",
                "-H", "referer: https://example.com/",
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
                
                # Detect actual resolution for filename
                res_label = "FINAL"
                try:
                    probe = subprocess.run(
                        ["ffprobe", "-v", "error", "-select_streams", "v:0",
                         "-show_entries", "stream=width,height", "-of", "csv=p=0",
                         str(video_decrypted)],
                        capture_output=True, text=True
                    )
                    if probe.returncode == 0 and probe.stdout.strip():
                        w, h = probe.stdout.strip().split(",")
                        res_label = f"{h}p"
                except Exception:
                    pass

                # Merge into course folder
                merged_file = save_dir / f"{filename}_{res_label}_FINAL.mp4"

                merge_cmd = [
                    "ffmpeg", "-i", str(video_decrypted), "-i", str(audio_decrypted),
                    "-c", "copy", "-map", "0:v:0", "-map", "1:a:0",
                    str(merged_file), "-y"
                ]
                
                result = subprocess.run(merge_cmd, capture_output=True)
                
                if result.returncode == 0:
                    # Download PDF if available
                    pdf_url = lesson.get('pdf_url', '')
                    if pdf_url:
                        try:
                            import requests as req
                            pdf_name = lesson.get('pdf_filename') or f"{filename}.pdf"
                            pdf_path = save_dir / pdf_name
                            print(f"📄 Downloading PDF: {pdf_name}")
                            r = req.get(pdf_url, timeout=30)
                            r.raise_for_status()
                            pdf_path.write_bytes(r.content)
                            print(f"✅ PDF saved: {pdf_path}")
                        except Exception as pdf_err:
                            print(f"⚠️  PDF download failed: {pdf_err}")

                    # Cleanup intermediate files
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
    
    def download_all(self, retry_only=False):
        """Download all lessons in parallel"""
        # Clean stale tmp dirs first
        self._clean_tmp_dirs()
        
        # Remove duplicates first
        removed = self.remove_duplicates()
        if removed > 0:
            print(f"✅ Removed {removed} duplicate(s)")
        
        queue = self.load_queue()
        
        if not queue:
            print("❌ Queue is empty!")
            print("\nStart server first: python twinvine.py server")
            return
        
        if retry_only:
            pending = [l for l in queue if l.get('status') == 'failed']
            if not pending:
                print("✅ No failed lessons to retry!")
                return
            # Reset them to pending
            for l in pending:
                l['status'] = 'pending'
            self.save_queue(queue)
            print(f"🔄 Retrying {len(pending)} failed lesson(s)...")
        else:
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
        # --yes flag skips confirmation
        yes = '--yes' in sys.argv
        if not yes:
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
                page_title = data.get('page_title', '')
                pdf_url = data.get('pdf_url', '')
                pdf_filename = data.get('pdf_filename', '')
                
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
                
                # Generate filename using a clean title extractor
                import re
                lesson_num = len(queue) + 1
                BRAND_WORDS = {'testbook', 'testbook.com', 'login', 'signup', 'home', 'dashboard', 'video', ''}

                def clean_title(raw):
                    """Clean a page/MPD title into a safe, readable filename."""
                    t = raw.strip()
                    for suffix in [' - Testbook', ' | Testbook', '- Testbook', '| Testbook',
                                   ' - testbook.com', ' | testbook.com']:
                        t = t.replace(suffix, '')
                    t = re.sub(r'\s+', ' ', t).strip().strip(' -|')
                    for ch in ['/', '\\', ':', '?', '*', '|', '"', '<', '>']:
                        t = t.replace(ch, '_')
                    t = t[:60].strip()
                    # Reject if it's just a brand/empty word
                    if t.lower() in BRAND_WORDS:
                        return ''
                    return t

                def url_fallback_title():
                    """Extract a title from the MPD URL hash as last resort."""
                    parts = mpd_url.rstrip('/').split('/')
                    # Use the directory hash before the .mpd filename
                    candidate = parts[-2] if len(parts) >= 2 else ''
                    return candidate[:20] if candidate else f'lesson{lesson_num:02d}'

                raw = page_title or metadata.get('title', '')
                clean = clean_title(raw) if raw else ''
                if not clean:
                    clean = url_fallback_title()
                    print(f"⚠️  Title was brand/empty — using URL fallback: {clean}")

                filename = f"lesson{lesson_num:02d}_{clean}"
                print(f"📝 Filename: {filename}")


                # Add to queue
                lesson = {
                    'number': lesson_num,
                    'filename': filename,
                    'mpd_url': mpd_url,
                    'keys': keys,
                    'metadata': metadata,
                    'page_title': page_title,
                    'pdf_url': pdf_url,
                    'pdf_filename': pdf_filename,
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
        
        @app.route('/save-pdf', methods=['POST'])
        def save_pdf_to_queue():
            """Save a PDF-only entry to auto_queue.json"""
            try:
                data = request.json
                pdf_url = data.get('pdf_url')
                pdf_name = data.get('pdf_name', '')

                if not pdf_url or not pdf_name:
                    return jsonify({'error': 'Missing pdf_url or pdf_name'}), 400

                queue = self.load_queue()

                # Deduplicate
                for entry in queue:
                    if entry.get('pdf_url') == pdf_url:
                        return jsonify({
                            'success': False,
                            'error': 'duplicate',
                            'existing': entry.get('pdf_name')
                        }), 200

                import re
                lesson_num = len(queue) + 1
                # Strip timestamp suffix e.g. _1758716557.pdf → clean name
                clean = re.sub(r'_\d{9,10}(\.pdf)?$', '', pdf_name, flags=re.IGNORECASE).strip()
                clean = re.sub(r'\.pdf$', '', clean, flags=re.IGNORECASE).strip()
                filename = f"lesson{lesson_num:02d}_{clean}"

                entry = {
                    'number': lesson_num,
                    'filename': filename,
                    'pdf_url': pdf_url,
                    'pdf_name': pdf_name,
                    'captured_at': datetime.now().isoformat(),
                    'status': 'pending'
                }

                queue.append(entry)
                self.save_queue(queue)

                print(f"\n📄 PDF saved to queue: {filename}")
                print(f"   🔗 {pdf_url[:80]}...")
                print(f"   📋 Queue: {len(queue)} entries")

                return jsonify({
                    'success': True,
                    'filename': filename,
                    'lesson_number': lesson_num,
                    'queue_length': len(queue)
                }), 200

            except Exception as e:
                print(f"❌ save-pdf error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @app.route('/health', methods=['GET'])
        def health():
            """Health check"""
            return jsonify({'status': 'running', 'queue_length': len(self.load_queue())})
        
        print("="*80)
        print("🎬 TwinVine Auto-Capture Server")
        print("="*80)
        print()
        port = int(os.environ.get('TWINVINE_PORT', 8765))
        print(f"Server running on http://localhost:{port}")
        print()
        print("How to use:")
        print("1. Keep this server running")
        print("2. Open browser extension")
        print("3. Play videos in browser")
        print("4. Extension automatically sends URLs here")
        print("5. Keys extracted and cached automatically")
        print("6. Later: python twinvine.py download")
        print()
        print("  Set TWINVINE_PORT env var to change port (default 8765)")
        print()
        print("="*80)
        print()
        
        app.run(host='localhost', port=port, debug=True, use_reloader=True)
    
    # ==================== SINGLE VIDEO MODE ====================
    
    def download_single(self):
        """Download a single video (manual mode using twinvine_core)"""
        print("="*80)
        print("🎬 TwinVine Single Video Downloader")
        print("="*80)
        print()
        
        wvd_path = "./WVDs/device.wvd"
        videos_downloaded = 0
        
        while True:
            mpd_url = input("📍 Paste the MPD URL (.mpd): ").strip()
            if not mpd_url:
                if videos_downloaded > 0:
                    print(f"\n🎉 Done! Downloaded {videos_downloaded} video(s)")
                    break
                print("❌ No URL provided.")
                sys.exit(1)
            
            license_url = input("🔐 Paste License URL (with token): ").strip()
            if not license_url or "getlicense" not in license_url:
                print("❌ Invalid license URL!")
                continue
            
            output_name = input("💾 Output filename (without extension): ").strip() or f"twinvine_{videos_downloaded+1:02d}"
            output_name = output_name.replace('/', '_').replace(':', '_').replace('?', '_')
            
            try:
                keys = get_keys(mpd_url, license_url, wvd_path)
                success = download_with_keys(mpd_url, keys, output_name)
                if success:
                    videos_downloaded += 1
                another = input("📥 Download another? (y/N): ").strip().lower()
                if another != 'y':
                    break
            except KeyboardInterrupt:
                print("\n⚠️  Interrupted")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                sys.exit(1)
    
    # ==================== RETRY FAILED ====================

    def retry_failed(self):
        """Retry all failed downloads"""
        self.download_all(retry_only=True)

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
        print("  python twinvine.py download    # Download all pending videos")
        print("  python twinvine.py retry       # Retry all failed downloads")
        print("  python twinvine.py single      # Download a single video (manual)")
        print("  python twinvine.py clear       # Clear queue")
        print()
        print("Options:")
        print("  --workers N    Parallel downloads (default: 3)")
        print("  --yes          Skip confirmation prompt")
        print()
        print("Examples:")
        print("  python twinvine.py server")
        print("  python twinvine.py download --workers 5")
        print("  python twinvine.py retry")
        print()
        print("  Set TWINVINE_PORT env var to change server port (default 8765)")
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
    
    tv = TwinVine(max_workers=max_workers)
    
    if command == 'server':
        tv.start_server()
    elif command == 'status':
        tv.show_status()
    elif command == 'download':
        tv.download_all()
    elif command == 'retry':
        tv.retry_failed()
    elif command == 'single':
        tv.download_single()
    elif command == 'clear':
        tv.clear_queue()
    else:
        print(f"❌ Unknown command: {command}")
        print("Use: server, status, download, retry, single, or clear")


if __name__ == "__main__":
    main()
