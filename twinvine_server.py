#!/usr/bin/env python3
"""
TwinVine Auto-Capture Server
Runs in background to receive URLs from browser extension and extract keys automatically

Usage:
1. Start this server: python twinvine_server.py
2. Open browser extension
3. Play videos - extension sends URLs here automatically
4. Keys are extracted and cached immediately
5. Later: python twinvine_auto.py download
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
from pathlib import Path
from datetime import datetime

# Import core functions
from twinvine_720p import get_keys, extract_metadata_from_mpd

app = Flask(__name__)
CORS(app)  # Allow extension to connect

# Cache directory
CACHE_DIR = Path("./vaults/course_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
QUEUE_FILE = CACHE_DIR / "auto_queue.json"

def load_queue():
    """Load queue from file"""
    if not QUEUE_FILE.exists():
        return []
    try:
        with open(QUEUE_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_queue(queue):
    """Save queue to file"""
    with open(QUEUE_FILE, 'w') as f:
        json.dump(queue, f, indent=2)

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
        queue = load_queue()
        
        # Check if this MPD URL already exists
        for lesson in queue:
            if lesson.get('mpd_url') == mpd_url:
                print(f"\n⚠️  Duplicate detected - MPD already in queue")
                print(f"   Lesson: {lesson.get('filename')}")
                return jsonify({
                    'success': False,
                    'error': 'duplicate',
                    'message': 'This video is already in the queue',
                    'existing_lesson': lesson.get('filename'),
                    'queue_length': len(queue)
                }), 200
        
        print(f"\n{'='*80}")
        print(f"🔑 Auto-extracting keys...")
        if page_title:
            print(f"📝 Page Title: {page_title}")
        print(f"{'='*80}")
        
        # Extract metadata
        print("📊 Extracting metadata...")
        try:
            metadata = extract_metadata_from_mpd(mpd_url)
            print(f"📝 MPD Title: {metadata.get('title', 'unknown')}")
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
            
            # Check if token expired
            if 'expired' in error_msg.lower() or '403' in error_msg:
                print("❌ Token expired!")
                print("   User needs to refresh the page and play video again")
                return jsonify({
                    'success': False,
                    'error': 'token_expired',
                    'message': 'License token has expired. Please refresh the page and play the video again.',
                    'queue_length': len(queue)
                }), 200
            
            # Other error
            print(f"❌ Key extraction failed: {error_msg}")
            return jsonify({
                'success': False,
                'error': 'extraction_failed',
                'message': f'Key extraction failed: {error_msg}',
                'queue_length': len(queue)
            }), 500
        
        if not keys:
            print("❌ No keys extracted")
            return jsonify({
                'success': False,
                'error': 'no_keys',
                'message': 'No keys were extracted from the license server',
                'queue_length': len(queue)
            }), 500
        
        print(f"✅ Extracted {len(keys)} keys")
        
        # Generate filename from page title or metadata
        lesson_num = len(queue) + 1
        
        if page_title:
            # Use page title (from extension)
            filename = page_title.strip()
            # Remove common suffixes
            filename = filename.replace(' - Testbook', '').replace(' | Testbook', '')
            # Clean invalid characters
            filename = filename.replace('/', '_').replace('\\', '_').replace(':', '_').replace('?', '_').replace('*', '_').replace('|', '_')
            filename = f"lesson{lesson_num:02d}_{filename[:50]}"
            print(f"📝 Using page title: {filename}")
        else:
            # Fallback to metadata title
            title = metadata.get('title', f'lesson{lesson_num:02d}')
            filename = f"lesson{lesson_num:02d}_{title[:20]}"
            filename = filename.replace('/', '_').replace('\\', '_').replace(':', '_').replace('?', '_').replace('*', '_')
            print(f"📝 Using metadata title: {filename}")
        
        # Add to queue
        lesson = {
            'number': lesson_num,
            'filename': filename,
            'mpd_url': mpd_url,
            'keys': keys,
            'metadata': metadata,
            'captured_at': datetime.now().isoformat(),
            'status': 'pending'
        }
        
        queue.append(lesson)
        save_queue(queue)
        
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
    queue = load_queue()
    return jsonify({
        'queue': queue,
        'total': len(queue),
        'pending': len([l for l in queue if l.get('status') == 'pending']),
        'downloaded': len([l for l in queue if l.get('status') == 'downloaded'])
    })

@app.route('/queue/clear', methods=['POST'])
def clear_queue():
    """Clear queue"""
    save_queue([])
    return jsonify({'success': True})

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({'status': 'running', 'queue_length': len(load_queue())})

def main():
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
    print("6. Later: python twinvine_auto.py download")
    print()
    print("="*80)
    print()
    
    # Check if flask-cors is installed
    try:
        import flask_cors
    except ImportError:
        print("⚠️  Installing flask-cors...")
        import subprocess
        subprocess.run(["uv", "pip", "install", "flask-cors"], check=True)
        print("✅ Installed flask-cors")
        print()
    
    app.run(host='localhost', port=8765, debug=False)

if __name__ == "__main__":
    main()
