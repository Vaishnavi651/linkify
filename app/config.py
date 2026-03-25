import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # MongoDB connection
    MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    DATABASE_NAME = "url_shortener"
    
    # App settings
    APP_NAME = "Linkify"
    APP_VERSION = "1.0.0"
    
    # Base URL
    BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
    
    # Port (for Render)
    PORT = int(os.getenv("PORT", 8000))

settings = Settings()