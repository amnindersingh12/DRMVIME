#!/usr/bin/env python3
"""
Filename Utilities
Helper functions for cleaning and processing filenames.
"""

import re
from typing import Optional

def clean_filename(filename: str) -> str:
    """
    Clean filename by removing timestamps and unwanted suffixes.
    
    Args:
        filename: Raw filename to clean
        
    Returns:
        Cleaned filename suitable for use
    """
    if not filename:
        return ''
    
    # Strip timestamp suffix like _1758716557 and .pdf
    clean = re.sub(r'_\d{9,10}(\.pdf)?$', '', filename, flags=re.IGNORECASE).strip()
    clean = re.sub(r'\.pdf$', '', clean, flags=re.IGNORECASE).strip()
    
    # Remove common brand words
    brand_words = ['testbook', 'testbook.com', 'login', 'signup', 'home', 'dashboard', 'video']
    for brand in brand_words:
        clean = re.sub(rf'\b{re.escape(brand)}\b', '', clean, flags=re.IGNORECASE)
    
    # Clean up whitespace and special characters
    clean = re.sub(r'\s+', ' ', clean).strip()
    clean = clean.strip(' -|')
    
    # Replace filesystem-unsafe characters
    for char in ['/', '\\', ':', '?', '*', '|', '"', '<', '>']:
        clean = clean.replace(char, '_')
    
    # Limit length
    clean = clean[:60].strip()
    
    return clean or 'untitled'

def extract_lesson_id(url: str) -> Optional[str]:
    """
    Extract lesson ID from various URL patterns.
    
    Args:
        url: URL to extract lesson ID from
        
    Returns:
        Lesson ID if found, None otherwise
    """
    if not url:
        return None
    
    # Pattern for testbook MPD URLs: /wv/{lessonId}/
    mpd_match = re.search(r'/wv/([a-f0-9]{20,})', url)
    if mpd_match:
        return mpd_match.group(1)
    
    # Pattern for PDF URLs with lesson ID
    pdf_match = re.search(r'/assets/([a-f0-9]{20,})/', url)
    if pdf_match:
        return pdf_match.group(1)
    
    # Generic pattern for long hex IDs
    generic_match = re.search(r'([a-f0-9]{20,})', url)
    if generic_match:
        return generic_match.group(1)
    
    return None

def generate_lesson_filename(lesson_number: int, title: str) -> str:
    """
    Generate standardized lesson filename.
    
    Args:
        lesson_number: Lesson sequence number
        title: Lesson title
        
    Returns:
        Formatted filename
    """
    clean_title = clean_filename(title) if title else 'untitled'
    return f"lesson{lesson_number:02d}_{clean_title}"