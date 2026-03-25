from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import Optional

class URLCreate(BaseModel):
    """Schema for creating a new short URL"""
    long_url: HttpUrl
    custom_code: Optional[str] = None
    expires_days: Optional[int] = None
    password: Optional[str] = None

class URLResponse(BaseModel):
    """Schema for returning URL data"""
    short_code: str
    short_url: str
    long_url: str
    created_at: datetime
    clicks: int
    expires_at: Optional[datetime] = None
    is_password_protected: bool = False
    
    class Config:
        from_attributes = True