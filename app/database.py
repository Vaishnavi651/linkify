from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

class Database:
    client = None
    db = None

db = Database()

async def connect_to_mongo():
    db.client = AsyncIOMotorClient(settings.MONGODB_URL)
    db.db = db.client[settings.DATABASE_NAME]
    await db.db.urls.create_index("short_code", unique=True)
    print("Connected to MongoDB!")

async def close_mongo_connection():
    if db.client:
        db.client.close()
        print("MongoDB connection closed!")

def get_db():
    return db.db