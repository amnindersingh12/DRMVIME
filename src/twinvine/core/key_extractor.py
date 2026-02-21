#!/usr/bin/env python3
"""
Key Extractor Module
Handles DRM key extraction using the existing twinvine_core functionality.
"""

import subprocess
import json
from typing import Dict, List, Any
from pathlib import Path

class KeyExtractor:
    """Handles DRM key extraction from MPD and license URLs."""
    
    def __init__(self, wvd_path: str = None):
        if wvd_path is None:
            wvd_path = Path(__file__).parent.parent.parent / "WVDs" / "device.wvd"
        
        self.wvd_path = Path(wvd_path)
        
        if not self.wvd_path.exists():
            raise FileNotFoundError(f"WVD file not found: {self.wvd_path}")
    
    def extract_keys(self, mpd_url: str, license_url: str) -> Dict[str, Any]:
        """
        Extract DRM keys using twinvine_core.
        
        Args:
            mpd_url: URL to the MPD manifest
            license_url: URL to the license server
            
        Returns:
            Dict containing success status, keys, metadata, and any error info
        """
        try:
            # Import the core extraction function
            from twinvine_core import extract_widevine_keys
            
            result = extract_widevine_keys(
                mpd_url=mpd_url,
                license_url=license_url,
                device_path=str(self.wvd_path)
            )
            
            if result.get('success'):
                return {
                    'success': True,
                    'keys': result.get('keys', []),
                    'metadata': self._extract_metadata(result, mpd_url)
                }
            else:
                error_msg = result.get('error', 'Unknown extraction error')
                
                # Check for common error patterns
                if 'expired' in error_msg.lower() or 'token' in error_msg.lower():
                    return {
                        'success': False,
                        'error': 'token_expired',
                        'message': 'License token has expired. Please refresh the page and play the video again.'
                    }
                else:
                    return {
                        'success': False,
                        'error': 'extraction_failed',
                        'message': f'Key extraction failed: {error_msg}'
                    }
                    
        except Exception as e:
            return {
                'success': False,
                'error': 'server_error',
                'message': f'Extraction error: {str(e)}'
            }
    
    def _extract_metadata(self, result: Dict, mpd_url: str) -> Dict[str, Any]:
        """Extract metadata from extraction result and MPD URL."""
        metadata = {
            'title': result.get('title', ''),
            'duration': result.get('duration', ''),
            'resolution': result.get('resolution', ''),
            'bitrate': result.get('bitrate', ''),
            'type': 'video'
        }
        
        # Try to extract additional info from MPD URL
        if 'testbook.com' in mpd_url:
            # Extract lesson ID from testbook URLs
            parts = mpd_url.split('/')
            if len(parts) >= 3:
                lesson_id = parts[-3] if parts[-3] != 'wv' else parts[-2]
                metadata['lesson_id'] = lesson_id
        
        # Clean up empty values
        return {k: v for k, v in metadata.items() if v}
    
    def validate_wvd(self) -> bool:
        """Validate that WVD file is accessible and valid."""
        try:
            return self.wvd_path.exists() and self.wvd_path.stat().st_size > 0
        except Exception:
            return False