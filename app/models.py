from datetime import datetime, timedelta
from typing import Optional

def url_document(short_code: str, long_url: str, custom_code: str = None, expires_days: int = None, password: str = None):
    """Create a URL document for MongoDB"""
    expires_at = None
    if expires_days:
        expires_at = datetime.utcnow() + timedelta(days=expires_days)
    
    return {
        "short_code": short_code,
        "long_url": long_url,
        "created_at": datetime.utcnow(),
        "clicks": 0,
        "is_active": True,
        "expires_at": expires_at,
        "password": password,
        "is_password_protected": password is not None
    }

def click_event_document(short_code: str, ip: str = None, user_agent: str = None):
    """Create a click event document for MongoDB"""
    return {
        "short_code": short_code,
        "clicked_at": datetime.utcnow(),
        "ip_address": ip,
        "user_agent": user_agent
    }