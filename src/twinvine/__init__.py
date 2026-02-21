#!/usr/bin/env python3
"""
TwinVine Package Initializer
Modularized TwinVine codebase for unified PDF and video capture.
"""

__version__ = "1.2.0"
__author__ = "TwinVine Team"
__description__ = "Automated DRM video downloader with unified PDF capture"

from .server import TwinVineServer
from .core.queue_manager import QueueManager
from .core.key_extractor import KeyExtractor
from .utils.filename_utils import clean_filename, extract_lesson_id, generate_lesson_filename
from .utils.api_utils import validate_pdf_request, validate_video_request, format_api_response

__all__ = [
    'TwinVineServer',
    'QueueManager', 
    'KeyExtractor',
    'clean_filename',
    'extract_lesson_id',
    'generate_lesson_filename',
    'validate_pdf_request',
    'validate_video_request',
    'format_api_response'
]