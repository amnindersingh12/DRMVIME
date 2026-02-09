#!/usr/bin/env python3
"""
TwinVine Auto Downloader
Downloads all videos from auto-captured queue in parallel

Workflow:
1. Start server: python twinvine_server.py
2. Browse course, play each video briefly (10 sec)
3. Extension auto-captures and extracts keys
4. Run: python twinvine_auto.py download
5. All videos download in parallel!

Commands:
  python twinvine_auto.py status     # Show queue status
  python twinvine_auto.py download   # Download all in parallel
  python twinvine_auto.py clear      # Clear queue
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

# Import download function
from twinvine_parallel import ParallelDownloader


class AutoDownloader:
    def __init__(self, max_workers=3):
        self.cache_dir = Path("./vaults/course_cache")
        self.queue_file = self.cache_dir / "auto_queue.json"
        self.max_workers = max_workers
        self.lock = threading.Lock()
        
    def load_queue(self):
        """Load auto-captured queue"""
        if not self.queue_file.exists():
            return []
        
        try:
            with open(self.queue_file, 'r') as f:
                return json.load(f)
        except:
            return []
    
    def save_queue(self, queue):
        """Save queue"""
        with self.lock:
            with open(self.queue_file, 'w') as f:
                json.dump(queue, f, indent=2)
    
    def show_status(self):
        """Show queue status"""
        queue = self.load_queue()
        
        if not queue:
            print("\n📋 Queue is empty")
            print("\nTo auto-capture:")
            print("1. Start server: python twinvine_server.py")
            print("2. Open browser extension")
            print("3. Play each video briefly (10 sec)")
            print("4. Extension auto-captures and extracts keys")
            print("5. Run: python twinvine_auto.py download")
            return
        
        print(f"\n📚 Auto-Captured Queue ({len(queue)} lessons)")
        print("="*80)
        
        for lesson in queue:
            status = lesson.get('status', 'pending')
            icon = '✅' if status == 'downloaded' else '⏳' if status == 'pending' else '❌'
            duration = lesson.get('metadata', {}).get('duration', '?')
            
            print(f"{icon} Lesson {lesson['number']:02d}: {lesson['filename']} ({duration})")
        
        pending = len([l for l in queue if l.get('status') == 'pending'])
        downloaded = len([l for l in queue if l.get('status') == 'downloaded'])
        
        print("="*80)
        print(f"✅ Downloaded: {downloaded}")
        print(f"⏳ Pending: {pending}")
        
        if pending > 0:
            print(f"\nReady to download! Run: python twinvine_auto.py download")
    
    def download_all(self):
        """Download all using parallel downloader"""
        queue = self.load_queue()
        
        if not queue:
            print("❌ Queue is empty!")
            print("\nStart server first: python twinvine_server.py")
            return
        
        pending = [l for l in queue if l.get('status') == 'pending']
        
        if not pending:
            print("✅ All lessons already downloaded!")
            return
        
        print("="*80)
        print("🚀 AUTO DOWNLOAD - Parallel Mode")
        print("="*80)
        print()
        print(f"📋 {len(pending)} lessons auto-captured and ready")
        print(f"⚡ Will download {self.max_workers} videos simultaneously")
        print()
        
        for lesson in pending[:5]:
            print(f"  • {lesson['filename']} ({lesson.get('metadata', {}).get('duration', '?')})")
        
        if len(pending) > 5:
            print(f"  ... and {len(pending) - 5} more")
        
        print()
        print("✨ All keys already extracted - no token expiration issues!")
        print()
        
        confirm = input(f"Start parallel download? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Cancelled")
            return
        
        # Use ParallelDownloader
        downloader = ParallelDownloader(max_workers=self.max_workers)
        
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
                executor.submit(downloader.download_single, lesson, queue): lesson 
                for lesson in pending
            }
            
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
        print(f"🎉 Auto Download Complete!")
        print(f"✅ Downloaded: {downloaded}/{len(pending)}")
        if failed > 0:
            print(f"❌ Failed: {failed}")
        print(f"⏱️  Total time: {int(elapsed/60)}m {int(elapsed%60)}s")
        print(f"⚡ Average: {int(elapsed/len(pending))}s per video")
        print("="*80)
    
    def clear_queue(self):
        """Clear queue"""
        confirm = input("⚠️  Clear entire queue? (y/N): ").strip().lower()
        if confirm == 'y':
            self.save_queue([])
            print("✅ Queue cleared")


def main():
    if len(sys.argv) < 2:
        print("="*80)
        print("🎬 TwinVine Auto Downloader")
        print("="*80)
        print()
        print("Fully automated course downloading!")
        print()
        print("Setup:")
        print("  1. Start server: python twinvine_server.py")
        print("  2. Open browser extension")
        print("  3. Play each video briefly (10 sec)")
        print("  4. Extension auto-captures and extracts keys")
        print()
        print("Commands:")
        print("  python twinvine_auto.py status     # Show queue")
        print("  python twinvine_auto.py download   # Download all")
        print("  python twinvine_auto.py clear      # Clear queue")
        print()
        print("Options:")
        print("  --workers N    Parallel downloads (default: 3)")
        print()
        print("Example:")
        print("  python twinvine_auto.py download --workers 5")
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
    
    downloader = AutoDownloader(max_workers=max_workers)
    
    if command == 'status':
        downloader.show_status()
    elif command == 'download':
        downloader.download_all()
    elif command == 'clear':
        downloader.clear_queue()
    else:
        print(f"❌ Unknown command: {command}")
        print("Use: status, download, or clear")


if __name__ == "__main__":
    main()
