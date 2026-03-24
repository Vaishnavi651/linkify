from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app import schemas, utils, models
from app.database import connect_to_mongo, close_mongo_connection, get_db
from app.config import settings

# Create FastAPI app
app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

# Mount static files (CSS, JS)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Set up templates
templates = Jinja2Templates(directory="app/templates")

@app.on_event("startup")
async def startup_event():
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown_event():
    await close_mongo_connection()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the homepage"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health_check():
    """Health check endpoint for uptime monitoring"""
    return {"status": "alive", "service": "Linkify"}

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard page - shows all URLs"""
    db = get_db()
    
    # Get all URLs from database
    urls = await db.urls.find().sort("created_at", -1).to_list(length=100)
    
    # Generate HTML for each URL
    urls_html = ""
    for url in urls:
        urls_html += f"""
        <div class="url-row">
            <div class="short-url-col">
                <a href="/{url['short_code']}" target="_blank" class="short-url-link">
                    {settings.BASE_URL}/{url['short_code']}
                </a>
            </div>
            <div class="long-url" title="{url['long_url']}">
                {url['long_url'][:50]}{'...' if len(url['long_url']) > 50 else ''}
            </div>
            <div class="clicks-count">{url.get('clicks', 0)}</div>
            <div class="created-date">{url['created_at'].strftime('%Y-%m-%d %H:%M')}</div>
        </div>
        """
    
    if not urls:
        urls_html = """
        <div class="empty-state">
            <div class="empty-state-icon">🔗</div>
            <h3>No URLs yet</h3>
            <p>Create your first short URL on the homepage!</p>
            <a href="/" style="display: inline-block; margin-top: 1rem; padding: 0.5rem 1rem; background: #3b82f6; color: white; text-decoration: none; border-radius: 8px;">Go to Homepage</a>
        </div>
        """
    
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dashboard - Linkify</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="/static/css/style.css">
    </head>
    <body>
        <nav class="navbar">
            <div class="nav-container">
                <div class="logo">
                    <span class="logo-icon">🔗</span>
                    <span class="logo-text">Linkify</span>
                </div>
                <div class="nav-links">
                    <a href="/" class="nav-link">Home</a>
                    <a href="/dashboard" class="nav-link active">Dashboard</a>
                </div>
            </div>
        </nav>

        <div class="dashboard-container">
            <div class="dashboard-header">
                <h1>📊 Your URLs</h1>
                <p>Track and manage all your shortened links</p>
            </div>

            <div class="urls-table">
                <div class="table-header">
                    <div>Short URL</div>
                    <div>Original URL</div>
                    <div>Clicks</div>
                    <div>Created</div>
                </div>
                {urls_html}
            </div>
        </div>

        <footer class="footer">
            <div class="footer-container">
                <p>&copy; 2026 Linkify - Make your links shorter and smarter</p>
            </div>
        </footer>
    </body>
    </html>
    """)

@app.post("/shorten")
async def create_short_url(url_data: schemas.URLCreate):
    """Create a shortened URL"""
    db = get_db()
    
    short_code = utils.generate_random_code()
    
    # Check if code exists
    existing = await db.urls.find_one({"short_code": short_code})
    while existing:
        short_code = utils.generate_random_code()
        existing = await db.urls.find_one({"short_code": short_code})
    
    url_doc = models.url_document(short_code, str(url_data.long_url))
    await db.urls.insert_one(url_doc)
    
    return {
        "short_code": short_code,
        "short_url": f"{settings.BASE_URL}/{short_code}",
        "long_url": str(url_data.long_url),
        "created_at": url_doc["created_at"],
        "clicks": 0
    }

@app.get("/{short_code}")
async def redirect_to_url(short_code: str, request: Request):
    """Redirect short URL to original URL"""
    db = get_db()
    
    url_data = await db.urls.find_one({"short_code": short_code, "is_active": True})
    
    if not url_data:
        raise HTTPException(status_code=404, detail="URL not found")
    
    # Update click count
    await db.urls.update_one(
        {"short_code": short_code},
        {"$inc": {"clicks": 1}}
    )
    
    # Record click event
    click_doc = models.click_event_document(
        short_code,
        request.client.host if request.client else None,
        request.headers.get("user-agent")
    )
    await db.click_events.insert_one(click_doc)
    
    return RedirectResponse(url=url_data["long_url"])