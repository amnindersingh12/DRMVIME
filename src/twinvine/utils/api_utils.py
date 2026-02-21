#!/usr/bin/env python3
"""
API Utilities
Helper functions for API request validation and processing.
"""

from typing import Dict, Optional

def validate_pdf_request(data: Dict) -> Optional[str]:
    """
    Validate PDF save request data.
    
    Args:
        data: Request data dictionary
        
    Returns:
        Error message if validation fails, None if valid
    """
    if not data:
        return 'No data provided'
    
    if not data.get('pdf_url'):
        return 'Missing pdf_url'
    
    if not data.get('pdf_name'):
        return 'Missing pdf_name'
    
    # Validate URL format
    pdf_url = data['pdf_url']
    if not pdf_url.startswith(('http://', 'https://')):
        return 'Invalid pdf_url format'
    
    # Validate filename
    pdf_name = data['pdf_name']
    if not isinstance(pdf_name, str) or len(pdf_name.strip()) == 0:
        return 'Invalid pdf_name'
    
    return None

def validate_video_request(data: Dict) -> Optional[str]:
    """
    Validate video key extraction request data.
    
    Args:
        data: Request data dictionary
        
    Returns:
        Error message if validation fails, None if valid
    """
    if not data:
        return 'No data provided'
    
    if not data.get('mpd_url'):
        return 'Missing mpd_url'
    
    if not data.get('license_url'):
        return 'Missing license_url'
    
    # Validate URL formats
    mpd_url = data['mpd_url']
    if not mpd_url.startswith(('http://', 'https://')) or not mpd_url.endswith('.mpd'):
        return 'Invalid mpd_url format'
    
    license_url = data['license_url']
    if not license_url.startswith(('http://', 'https://')):
        return 'Invalid license_url format'
    
    return None

def format_api_response(success: bool, data: Dict = None, error: str = None) -> Dict:
    """
    Format standardized API response.
    
    Args:
        success: Whether the operation was successful
        data: Response data for successful operations
        error: Error message for failed operations
        
    Returns:
        Formatted response dictionary
    """
    response = {'success': success}
    
    if success and data:
        response.update(data)
    elif not success and error:
        response['error'] = error
    
    return response