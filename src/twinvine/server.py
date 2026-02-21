#!/usr/bin/env python3
"""
TwinVine Server Module
Handles PDF URL capture and video key extraction with unified queue management.
"""

import json
import os
import re
from datetime import datetime
from flask import Flask, request, jsonify
from pathlib import Path

from .core.queue_manager import QueueManager
from .core.key_extractor import KeyExtractor
from .utils.filename_utils import clean_filename, extract_lesson_id
from .utils.api_utils import validate_pdf_request, validate_video_request

class TwinVineServer:
    """Main server class for handling PDF and video capture requests."""
    
    def __init__(self, host='localhost', port=8765, queue_path=None):
        self.app = Flask(__name__)
        self.host = host
        self.port = port
        
        # Initialize components
        self.queue_manager = QueueManager(queue_path)
        self.key_extractor = KeyExtractor()
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup Flask routes."""
        self.app.route('/health')(self.health_check)
        self.app.route('/save-pdf', methods=['POST'])(self.save_pdf)
        self.app.route('/extract-keys', methods=['POST'])(self.extract_keys)
    
    def health_check(self):
        """Health check endpoint."""
        queue_length = len(self.queue_manager.get_queue())
        return jsonify({
            'status': 'ok',
            'queue_length': queue_length
        })
    
    def save_pdf(self):
        """Save PDF URL to queue, merging with existing video entries if possible."""
        try:
            data = request.json
            validation_error = validate_pdf_request(data)
            if validation_error:
                return jsonify({'error': validation_error}), 400
            
            pdf_url = data['pdf_url']
            pdf_name = data['pdf_name']
            page_title = data.get('page_title', '')
            
            result = self.queue_manager.add_pdf_entry(
                pdf_url, pdf_name, page_title
            )
            
            if result['success']:
                return jsonify({
                    'success': True,
                    'filename': result['filename'],
                    'lesson_number': result['lesson_number'],
                    'queue_length': result['queue_length'],
                    'updated': result.get('updated', False)
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': result['error'],
                    'existing': result.get('existing')
                }), 200
                
        except Exception as e:
            return jsonify({
                'success': False,
                'error': 'server_error',
                'message': str(e)
            }), 500
    
    def extract_keys(self):
        """Extract DRM keys and save to queue, merging with existing PDF entries if possible."""
        try:
            data = request.json
            validation_error = validate_video_request(data)
            if validation_error:
                return jsonify({'error': validation_error}), 400
            
            mpd_url = data['mpd_url']
            license_url = data['license_url']
            page_title = data.get('page_title', '')
            
            # Extract keys
            keys_result = self.key_extractor.extract_keys(mpd_url, license_url)
            if not keys_result['success']:
                return jsonify({
                    'success': False,
                    'error': keys_result['error'],
                    'message': keys_result['message']
                }), 500
            
            # Add to queue
            result = self.queue_manager.add_video_entry(
                mpd_url, keys_result['keys'], keys_result['metadata'], 
                page_title
            )
            
            if result['success']:
                return jsonify({
                    'success': True,
                    'message': 'Keys extracted and added to queue',
                    'lesson_number': result['lesson_number'],
                    'filename': result['filename'],
                    'keys': keys_result['keys'],
                    'metadata': keys_result['metadata'],
                    'queue_length': result['queue_length'],
                    'updated': result.get('updated', False)
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': result['error'],
                    'message': result['message']
                }), 500
                
        except Exception as e:
            return jsonify({
                'success': False,
                'error': 'server_error',
                'message': str(e)
            }), 500
    
    def run(self, debug=True):
        """Start the Flask server."""
        print("=" * 80)
        print("🎬 TwinVine Auto-Capture Server")
        print("=" * 80)
        print(f"\nServer running on http://{self.host}:{self.port}")
        print("\nHow to use:")
        print("1. Keep this server running")
        print("2. Open browser extension")
        print("3. Play videos in browser")
        print("4. Extension automatically sends URLs here")
        print("5. Keys extracted and cached automatically")
        print("6. Later: python twinvine_auto.py download")
        print("\n" + "=" * 80 + "\n")
        
        self.app.run(
            host=self.host,
            port=self.port,
            debug=debug
        )

if __name__ == '__main__':
    server = TwinVineServer()
    server.run()