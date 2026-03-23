import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    DATABASE_NAME = "url_shortener"
    APP_NAME = "URL Shortener"
    APP_VERSION = "1.0.0"
    BASE_URL = "http://localhost:8000"

settings = Settings()