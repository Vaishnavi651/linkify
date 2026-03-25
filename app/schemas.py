from pydantic import BaseModel, HttpUrl, EmailStr
from datetime import datetime
from typing import Optional

class URLCreate(BaseModel):
    long_url: HttpUrl
    custom_code: Optional[str] = None
    expires_days: Optional[int] = None
    password: Optional[str] = None

class URLResponse(BaseModel):
    short_code: str
    short_url: str
    long_url: str
    created_at: datetime
    clicks: int
    expires_at: Optional[datetime] = None
    is_password_protected: bool = False
    
    class Config:
        from_attributes = True

# User schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    email: str
    created_at: datetime