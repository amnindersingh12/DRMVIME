#!/usr/bin/env python3
"""
Queue Manager Module
Handles unified queue operations for PDF and video entries.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from ..utils.filename_utils import clean_filename, extract_lesson_id

class QueueManager:
    """Manages the unified queue for PDF and video entries."""
    
    def __init__(self, queue_path: Optional[str] = None):
        if queue_path is None:
            queue_path = Path(__file__).parent.parent.parent / "vaults" / "course_cache" / "auto_queue.json"
        
        self.queue_path = Path(queue_path)
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize empty queue if doesn't exist
        if not self.queue_path.exists():
            self.save_queue([])
    
    def load_queue(self) -> List[Dict[str, Any]]:
        """Load queue from JSON file."""
        try:
            with open(self.queue_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def save_queue(self, queue: List[Dict[str, Any]]) -> None:
        """Save queue to JSON file."""
        with open(self.queue_path, 'w') as f:
            json.dump(queue, f, indent=2)
    
    def get_queue(self) -> List[Dict[str, Any]]:
        """Get current queue."""
        return self.load_queue()
    
    def find_existing_entry(self, queue: List[Dict], search_criteria: Dict) -> Optional[Dict]:
        """Find existing entry in queue based on search criteria."""
        for entry in queue:
            if self._matches_criteria(entry, search_criteria):
                return entry
        return None
    
    def _matches_criteria(self, entry: Dict, criteria: Dict) -> bool:
        """Check if entry matches search criteria."""
        # Check for PDF URL match
        if 'pdf_url' in criteria and entry.get('pdf_url') == criteria['pdf_url']:
            return True
        
        # Check for lesson ID match between PDF and video
        if 'lesson_id_match' in criteria:
            video_id = criteria['lesson_id_match']
            pdf_url = entry.get('pdf_url', '')
            return video_id in pdf_url
        
        return False
    
    def add_pdf_entry(self, pdf_url: str, pdf_name: str, page_title: str = '') -> Dict[str, Any]:
        """Add PDF entry to queue, merging with existing video entries if possible."""
        queue = self.load_queue()
        
        # Check for duplicate PDF URL
        existing_pdf = self.find_existing_entry(queue, {'pdf_url': pdf_url})
        if existing_pdf:
            return {
                'success': False,
                'error': 'duplicate',
                'existing': existing_pdf.get('filename')
            }
        
        # Check for existing video entry to update
        video_entry = self._find_matching_video_entry(queue, pdf_url)
        
        if video_entry:
            return self._update_video_with_pdf(video_entry, pdf_url, pdf_name, page_title)
        else:
            return self._create_pdf_only_entry(queue, pdf_url, pdf_name, page_title)
    
    def add_video_entry(self, mpd_url: str, keys: List[str], metadata: Dict, page_title: str = '') -> Dict[str, Any]:
        """Add video entry to queue, merging with existing PDF entries if possible."""
        queue = self.load_queue()
        
        # Check for existing PDF entry to update
        pdf_entry = self._find_matching_pdf_entry(queue, mpd_url)
        
        if pdf_entry:
            return self._update_pdf_with_video(pdf_entry, mpd_url, keys, metadata, page_title)
        else:
            return self._create_video_only_entry(queue, mpd_url, keys, metadata, page_title)
    
    def _find_matching_video_entry(self, queue: List[Dict], pdf_url: str) -> Optional[Dict]:
        """Find video entry that matches the PDF lesson ID."""
        pdf_parts = pdf_url.split('/')
        for entry in queue:
            if entry.get('mpd_url') and not entry.get('pdf_url'):
                mpd_parts = entry['mpd_url'].split('/')
                # Look for common lesson ID patterns
                if any(part in pdf_parts for part in mpd_parts[-3:-1] if len(part) > 10):
                    return entry
        return None
    
    def _find_matching_pdf_entry(self, queue: List[Dict], mpd_url: str) -> Optional[Dict]:
        """Find PDF entry that matches the video lesson ID."""
        mpd_parts = mpd_url.split('/')
        for entry in queue:
            if entry.get('pdf_url') and not entry.get('mpd_url'):
                pdf_parts = entry['pdf_url'].split('/')
                # Look for common lesson ID patterns
                if any(part in pdf_parts for part in mpd_parts[-3:-1] if len(part) > 10):
                    return entry
        return None
    
    def _update_video_with_pdf(self, video_entry: Dict, pdf_url: str, pdf_name: str, page_title: str) -> Dict[str, Any]:
        """Update existing video entry with PDF data."""
        clean_name = clean_filename(pdf_name)
        
        video_entry['pdf_url'] = pdf_url
        video_entry['pdf_filename'] = pdf_name
        video_entry['captured_at'] = datetime.now().isoformat()
        
        # Update title if current title looks like a hash
        current_title = video_entry.get('metadata', {}).get('title', '')
        if len(current_title) < 3 or re.match(r'^[a-f0-9]{15,}$', current_title):
            video_entry['metadata']['title'] = clean_name
            new_filename = f"lesson{video_entry['number']:02d}_{clean_name}"
            video_entry['filename'] = new_filename
        
        queue = self.load_queue()
        self.save_queue(queue)
        
        return {
            'success': True,
            'filename': video_entry['filename'],
            'lesson_number': video_entry['number'],
            'queue_length': len(queue),
            'updated': True
        }
    
    def _update_pdf_with_video(self, pdf_entry: Dict, mpd_url: str, keys: List[str], metadata: Dict, page_title: str) -> Dict[str, Any]:
        """Update existing PDF entry with video data."""
        pdf_entry['mpd_url'] = mpd_url
        pdf_entry['keys'] = keys
        pdf_entry['metadata'] = metadata
        pdf_entry['captured_at'] = datetime.now().isoformat()
        
        # Update title if we have a better one
        clean_title = clean_filename(page_title) if page_title else ''
        if clean_title and len(clean_title) > 5:
            pdf_entry['metadata']['title'] = clean_title
            new_filename = f"lesson{pdf_entry['number']:02d}_{clean_title}"
            pdf_entry['filename'] = new_filename
        
        queue = self.load_queue()
        self.save_queue(queue)
        
        return {
            'success': True,
            'filename': pdf_entry['filename'],
            'lesson_number': pdf_entry['number'],
            'queue_length': len(queue),
            'updated': True
        }
    
    def _create_pdf_only_entry(self, queue: List[Dict], pdf_url: str, pdf_name: str, page_title: str) -> Dict[str, Any]:
        """Create new PDF-only entry."""
        lesson_num = len(queue) + 1
        clean_name = clean_filename(pdf_name)
        filename = f"lesson{lesson_num:02d}_{clean_name}"
        
        entry = {
            'number': lesson_num,
            'filename': filename,
            'mpd_url': None,
            'keys': [],
            'metadata': {
                'title': clean_name,
                'duration': 'PDF',
                'type': 'pdf'
            },
            'pdf_url': pdf_url,
            'pdf_filename': pdf_name,
            'captured_at': datetime.now().isoformat(),
            'status': 'pending'
        }
        
        queue.append(entry)
        self.save_queue(queue)
        
        return {
            'success': True,
            'filename': filename,
            'lesson_number': lesson_num,
            'queue_length': len(queue)
        }
    
    def _create_video_only_entry(self, queue: List[Dict], mpd_url: str, keys: List[str], metadata: Dict, page_title: str) -> Dict[str, Any]:
        """Create new video-only entry."""
        lesson_num = len(queue) + 1
        clean_title = clean_filename(page_title) if page_title else f'lesson{lesson_num:02d}'
        filename = f"lesson{lesson_num:02d}_{clean_title}"
        
        entry = {
            'number': lesson_num,
            'filename': filename,
            'mpd_url': mpd_url,
            'keys': keys,
            'metadata': metadata,
            'page_title': page_title,
            'pdf_url': None,
            'pdf_filename': None,
            'captured_at': datetime.now().isoformat(),
            'status': 'pending'
        }
        
        queue.append(entry)
        self.save_queue(queue)
        
        return {
            'success': True,
            'filename': filename,
            'lesson_number': lesson_num,
            'queue_length': len(queue)
        }