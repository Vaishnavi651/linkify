from datetime import datetime, timedelta
from typing import Optional

# User model
def user_document(email: str, password_hash: str):
    """Create a user document"""
    return {
        "email": email,
        "password_hash": password_hash,
        "created_at": datetime.utcnow(),
        "is_active": True
    }

def session_document(user_id: str, token: str):
    """Create a session document"""
    return {
        "user_id": user_id,
        "token": token,
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(days=30)
    }

# URL model (add user_id field)
def url_document(short_code: str, long_url: str, user_id: str = None, custom_code: str = None, expires_days: int = None, password: str = None):
    """Create a URL document"""
    expires_at = None
    if expires_days:
        expires_at = datetime.utcnow() + timedelta(days=expires_days)
    
    return {
        "short_code": short_code,
        "long_url": long_url,
        "user_id": user_id,  # NEW: link to user
        "created_at": datetime.utcnow(),
        "clicks": 0,
        "is_active": True,
        "expires_at": expires_at,
        "password": password,
        "is_password_protected": password is not None
    }

def click_event_document(short_code: str, ip: str = None, user_agent: str = None):
    """Create a click event document"""
    return {
        "short_code": short_code,
        "clicked_at": datetime.utcnow(),
        "ip_address": ip,
        "user_agent": user_agent
    }