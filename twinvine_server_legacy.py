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
from twinvine_core import get_keys, extract_metadata_from_mpd

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
        page_title = data.get('page_title', '')
        pdf_url = data.get('pdf_url', '')
        pdf_filename = data.get('pdf_filename', '')
        
        if not mpd_url or not license_url:
            return jsonify({'error': 'Missing URLs'}), 400
        
        # Load queue to check for duplicates
        queue = load_queue()
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
        
        # Read WVD path from environment
        wvd_path = "./WVDs/device.wvd"
        
        try:
            keys = get_keys(mpd_url, license_url, wvd_path)
        except Exception as e:
            error_msg = str(e)
            
            # Check for token expiration
            if 'expired' in error_msg.lower() or '403' in error_msg:
                print("❌ Token expired!")
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
        
        # Generate filename using a clean title extractor
        import re
        lesson_num = len(queue) + 1
        BRAND_WORDS = {'testbook', 'testbook.com', 'login', 'signup', 'home', 'dashboard', 'video', ''}

        def clean_title(raw):
            t = raw.strip()
            for suffix in [' - Testbook', ' | Testbook', '- Testbook', '| Testbook',
                           ' - testbook.com', ' | testbook.com']:
                t = t.replace(suffix, '')
            t = re.sub(r'\s+', ' ', t).strip().strip(' -|')
            for ch in ['/', '\\', ':', '?', '*', '|', '"', '<', '>']:
                t = t.replace(ch, '_')
            t = t[:60].strip()
            if t.lower() in BRAND_WORDS:
                return ''
            return t

        def url_fallback_title():
            parts = mpd_url.rstrip('/').split('/')
            candidate = parts[-2] if len(parts) >= 2 else ''
            return candidate[:20] if candidate else f'lesson{lesson_num:02d}'

        raw = page_title or metadata.get('title', '')
        clean = clean_title(raw) if raw else ''
        if not clean:
            clean = url_fallback_title()
            print(f"⚠️  Title was brand/empty — using URL fallback: {clean}")

        # Check if there's already a PDF entry for this lesson that we should UPDATE
        pdf_entry = None
        for entry in queue:
            if (entry.get('pdf_url') and not entry.get('mpd_url')):
                # Check if PDF URL contains similar lesson ID
                pdf_parts = entry.get('pdf_url', '').split('/')
                mpd_parts = mpd_url.split('/')
                # Look for common lesson ID patterns
                if any(part in pdf_parts for part in mpd_parts[-3:-1] if len(part) > 10):
                    pdf_entry = entry
                    print(f"📄 Found existing PDF entry to update with video: {entry.get('filename')}")
                    break
        
        if pdf_entry:
            # UPDATE existing PDF entry with video data
            print(f"🔄 Updating existing PDF entry with video data")
            pdf_entry['mpd_url'] = mpd_url
            pdf_entry['keys'] = keys
            pdf_entry['metadata'] = metadata
            pdf_entry['page_title'] = page_title
            pdf_entry['pdf_url'] = pdf_url
            pdf_entry['pdf_filename'] = pdf_filename
            pdf_entry['captured_at'] = datetime.now().isoformat()
            
            # Update title if we have a better one
            if raw and clean and len(clean) > 5:
                pdf_entry['metadata']['title'] = clean
                new_filename = f"lesson{pdf_entry['number']:02d}_{clean}"
                pdf_entry['filename'] = new_filename
                print(f"📝 Updated filename: {new_filename}")
            
            save_queue(queue)
            
            print(f"✅ Updated existing PDF entry with video data: {pdf_entry['filename']}")
            print(f"📋 Queue still has {len(queue)} lessons")
            print(f"{'='*80}\n")
            
            return jsonify({
                'success': True,
                'message': 'Keys extracted and merged with existing PDF entry',
                'lesson_number': pdf_entry['number'],
                'filename': pdf_entry['filename'],
                'keys': keys,
                'metadata': metadata,
                'queue_length': len(queue),
                'updated': True
            }), 200
        
        else:
            # CREATE new video-only entry (will have None PDF fields)
            lesson_num = len(queue) + 1
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
            save_queue(queue)
            
            print(f"✅ Added to queue: {filename}")
            print(f"📋 Queue now has {len(queue)} lessons")
            print(f"{'='*80}\n")
        
        return jsonify({
            'success': True,
            'message': 'Keys extracted and added to queue',
            'lesson_number': lesson_num,
            'filename': filename,
            'keys': keys,
            'metadata': metadata,
            'queue_length': len(queue)
        }), 200

    except Exception as e:
        print(f"❌ Server error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'server_error',
            'message': str(e)
        }), 500

@app.route('/save-pdf', methods=['POST'])
def save_pdf_to_queue():
    """Save a PDF-only lesson entry to auto_queue.json"""
    try:
        data = request.json
        pdf_url = data.get('pdf_url')
        pdf_name = data.get('pdf_name', '')

        if not pdf_url or not pdf_name:
            return jsonify({'error': 'Missing pdf_url or pdf_name'}), 400

        queue = load_queue()

        # Check for existing PDF URL
        for entry in queue:
            if entry.get('pdf_url') == pdf_url:
                return jsonify({
                    'success': False,
                    'error': 'duplicate',
                    'existing': entry.get('filename')
                }), 200
        
        # Check if there's already a video entry for this lesson that we should UPDATE
        # Extract lesson ID from PDF URL to find matching video entries
        video_entry = None
        pdf_parts = pdf_url.split('/')
        if len(pdf_parts) >= 2:
            for entry in queue:
                if (entry.get('mpd_url') and not entry.get('pdf_url')):
                    mpd_parts = entry.get('mpd_url', '').split('/')
                    # Look for common lesson ID patterns
                    if any(part in pdf_parts for part in mpd_parts[-3:-1] if len(part) > 10):
                        video_entry = entry
                        print(f"🎬 Found existing video entry to update with PDF: {entry.get('filename')}")
                        break

        import re
        # Strip timestamp suffix like _1758716557 and .pdf for clean name
        clean = re.sub(r'_\d{9,10}(\.pdf)?$', '', pdf_name, flags=re.IGNORECASE).strip()
        clean = re.sub(r'\.pdf$', '', clean, flags=re.IGNORECASE).strip()
        
        if video_entry:
            # UPDATE existing video entry with PDF data
            print(f"🔄 Updating existing video entry with PDF data")
            video_entry['pdf_url'] = pdf_url
            video_entry['pdf_filename'] = pdf_name
            video_entry['captured_at'] = datetime.now().isoformat()
            
            # Update title if current title looks like a hash
            current_title = video_entry.get('metadata', {}).get('title', '')
            if len(current_title) < 3 or re.match(r'^[a-f0-9]{15,}$', current_title):
                video_entry['metadata']['title'] = clean
                new_filename = f"lesson{video_entry['number']:02d}_{clean}"
                video_entry['filename'] = new_filename
                print(f"📝 Updated filename: {new_filename}")
            
            save_queue(queue)
            
            print(f"✅ Updated existing video entry with PDF data: {video_entry['filename']}")
            print(f"📋 Queue still has {len(queue)} lessons")
            
            return jsonify({
                'success': True,
                'filename': video_entry['filename'],
                'lesson_number': video_entry['number'],
                'queue_length': len(queue),
                'updated': True
            }), 200
        
        else:
            # CREATE new PDF-only entry (same format as video entries)
            lesson_num = len(queue) + 1
            filename = f"lesson{lesson_num:02d}_{clean}"

            entry = {
                'number': lesson_num,
                'filename': filename,
                'mpd_url': None,  # No video for PDF-only lessons
                'keys': [],       # No keys for PDF-only lessons
                'metadata': {
                    'title': clean,
                    'duration': 'PDF',
                    'type': 'pdf'
                },
                'pdf_url': pdf_url,
                'pdf_filename': pdf_name,
                'captured_at': datetime.now().isoformat(),
                'status': 'pending'
            }

            queue.append(entry)
            save_queue(queue)

            print(f"📄 Saved PDF to queue: {filename}")
            print(f"🔗 URL: {pdf_url[:80]}...")
            print(f"📋 Queue now has {len(queue)} entries")

            return jsonify({
                'success': True,
                'filename': filename,
                'lesson_number': lesson_num,
                'queue_length': len(queue)
            }), 200

    except Exception as e:
        print(f"❌ save-pdf error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/download-pdf', methods=['POST'])
def download_pdf():
    """Download PDF from captured URL with authentication"""
    try:
        data = request.json
        pdf_url = data.get('pdf_url')
        pdf_filename = data.get('pdf_filename', 'document.pdf')
        page_title = data.get('page_title', '')
        cookies = data.get('cookies', '')  # Browser cookies for auth
        headers = data.get('headers', {})  # Browser headers
        
        if not pdf_url:
            return jsonify({'error': 'Missing pdf_url'}), 400
        
        print(f"\n{'='*80}")
        print(f"📄 Downloading DRM-Protected PDF...")
        print(f"{'='*80}")
        print(f"📝 Filename: {pdf_filename}")
        print(f"🔗 URL: {pdf_url[:80]}...")
        
        # Import requests
        import requests
        
        # Create downloads directory
        downloads_dir = Path("./downloads/PDFs")
        downloads_dir.mkdir(parents=True, exist_ok=True)
        
        # Clean filename
        safe_filename = pdf_filename.replace('/', '_').replace('\\', '_')
        output_path = downloads_dir / safe_filename
        
        # Prepare headers with authentication
        req_headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/pdf,*/*',
            'Referer': 'https://testbook.com/',
            'Origin': 'https://testbook.com'
        }
        
        # Add custom headers from browser
        if headers:
            req_headers.update(headers)
        
        # Parse cookies string into dict
        cookie_dict = {}
        if cookies:
            for cookie in cookies.split('; '):
                if '=' in cookie:
                    key, val = cookie.split('=', 1)
                    cookie_dict[key] = val
        
        print(f"🔐 Using {len(cookie_dict)} cookies for authentication")
        
        # Download with auth
        response = requests.get(
            pdf_url, 
            stream=True, 
            timeout=30,
            headers=req_headers,
            cookies=cookie_dict,
            allow_redirects=True
        )
        response.raise_for_status()
        
        # Check if we got a PDF
        content_type = response.headers.get('content-type', '')
        if 'pdf' not in content_type.lower() and 'octet-stream' not in content_type.lower():
            print(f"⚠️ Warning: Content-Type is '{content_type}', not PDF")
            print(f"📝 Response preview: {response.content[:200]}")
            
            # Might be an auth error page
            if b'<html' in response.content[:500] or b'login' in response.content[:500].lower():
                return jsonify({
                    'success': False,
                    'error': 'auth_required',
                    'message': 'PDF requires authentication. Make sure you are logged in to TestBook.',
                    'content_preview': response.content[:500].decode('utf-8', errors='ignore')
                }), 401
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    print(f"\r⏳ Progress: {percent:.1f}%", end='', flush=True)
        
        print()
        file_size = output_path.stat().st_size / (1024 * 1024)
        
        # Verify it's actually a PDF
        with open(output_path, 'rb') as f:
            header = f.read(4)
            if header != b'%PDF':
                print(f"❌ Downloaded file is not a valid PDF (header: {header})")
                output_path.unlink()
                return jsonify({
                    'success': False,
                    'error': 'invalid_pdf',
                    'message': 'Downloaded file is not a valid PDF. It may be DRM-protected or require special authentication.'
                }), 500
        
        print(f"✅ PDF saved: {output_path}")
        print(f"📊 Size: {file_size:.2f} MB")
        print(f"{'='*80}\n")
        
        return jsonify({
            'success': True,
            'message': 'PDF downloaded successfully',
            'filename': safe_filename,
            'path': str(output_path),
            'size_mb': round(file_size, 2)
        }), 200
        
    except Exception as e:
        print(f"❌ PDF download failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'download_failed',
            'message': str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint for the browser extension"""
    try:
        queue = load_queue()
        qlen = len(queue)
    except:
        qlen = 0
    return jsonify({
        'status': 'ok',
        'queue_length': qlen
    }), 200

if __name__ == '__main__':
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
    
    app.run(host='localhost', port=8765, debug=True, use_reloader=True)
