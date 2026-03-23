from pydantic import BaseModel, HttpUrl
from datetime import datetime

class URLCreate(BaseModel):
    long_url: HttpUrl

class URLResponse(BaseModel):
    short_code: str
    short_url: str
    long_url: str
    created_at: datetime
    clicks: int