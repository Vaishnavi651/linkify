from datetime import datetime

def url_document(short_code, long_url):
    return {
        "short_code": short_code,
        "long_url": long_url,
        "created_at": datetime.utcnow(),
        "clicks": 0,
        "is_active": True
    }

def click_event_document(short_code, ip=None, user_agent=None):
    return {
        "short_code": short_code,
        "clicked_at": datetime.utcnow(),
        "ip_address": ip,
        "user_agent": user_agent
    }