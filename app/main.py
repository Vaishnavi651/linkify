from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app import schemas, utils, models
from app.database import connect_to_mongo, close_mongo_connection, get_db
from app.config import settings
from app.qrcode import generate_qr_code
from datetime import datetime, timedelta

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
    
    urls = await db.urls.find().sort("created_at", -1).to_list(length=100)
    
    urls_html = ""
    for url in urls:
        # Add QR code link
        qr_link = f"/qr/{url['short_code']}"
        
        urls_html += f"""
        <div class="url-row">
            <div class="short-url-col">
                <a href="/{url['short_code']}" target="_blank" class="short-url-link">
                    {settings.BASE_URL}/{url['short_code']}
                </a>
                <a href="{qr_link}" target="_blank" class="qr-icon" style="margin-left: 10px; text-decoration: none;">📱</a>
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
    """Create a shortened URL with custom code, expiration, password"""
    db = get_db()
    
    # Use custom code if provided
    if url_data.custom_code:
        short_code = url_data.custom_code
        # Check if custom code already exists
        existing = await db.urls.find_one({"short_code": short_code})
        if existing:
            raise HTTPException(status_code=400, detail="Custom code already taken")
    else:
        short_code = utils.generate_random_code()
        existing = await db.urls.find_one({"short_code": short_code})
        while existing:
            short_code = utils.generate_random_code()
            existing = await db.urls.find_one({"short_code": short_code})
    
    # Create URL document with all features
    url_doc = models.url_document(
        short_code, 
        str(url_data.long_url),
        url_data.custom_code,
        url_data.expires_days,
        url_data.password
    )
    await db.urls.insert_one(url_doc)
    
    response = {
        "short_code": short_code,
        "short_url": f"{settings.BASE_URL}/{short_code}",
        "long_url": str(url_data.long_url),
        "created_at": url_doc["created_at"],
        "clicks": 0
    }
    
    if url_doc.get("expires_at"):
        response["expires_at"] = url_doc["expires_at"]
    if url_doc.get("is_password_protected"):
        response["is_password_protected"] = True
    
    return response

@app.get("/qr/{short_code}")
async def get_qr_code(short_code: str):
    """Generate QR code for a short URL"""
    db = get_db()
    
    url_data = await db.urls.find_one({"short_code": short_code})
    if not url_data:
        raise HTTPException(status_code=404, detail="URL not found")
    
    short_url = f"{settings.BASE_URL}/{short_code}"
    qr_img = generate_qr_code(short_url)
    
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>QR Code - Linkify</title>
        <style>
            body {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                text-align: center;
                padding: 50px;
                background: #0a0a0a;
                color: white;
            }}
            .qr-container {{
                background: white;
                padding: 20px;
                border-radius: 10px;
                display: inline-block;
                margin: 20px;
            }}
            .info {{
                margin-top: 20px;
            }}
            a {{
                color: #00d2ff;
                text-decoration: none;
                background: rgba(255,255,255,0.1);
                padding: 10px 20px;
                border-radius: 10px;
                display: inline-block;
                margin-top: 20px;
            }}
            a:hover {{
                background: rgba(255,255,255,0.2);
            }}
            .short-url {{
                font-family: monospace;
                color: #00d2ff;
                margin: 10px 0;
            }}
        </style>
    </head>
    <body>
        <h1>📱 QR Code for your link</h1>
        <div class="qr-container">
            <img src="data:image/png;base64,{qr_img}" alt="QR Code">
        </div>
        <div class="info">
            <p class="short-url">🔗 {short_url}</p>
            <p>Scan this QR code to visit the link instantly!</p>
        </div>
        <a href="/dashboard">← Back to Dashboard</a>
        <br><br>
        <a href="/">Home</a>
    </body>
    </html>
    """)

@app.get("/{short_code}")
async def redirect_to_url(short_code: str, request: Request, password: str = None):
    """Redirect short URL to original URL (with password protection)"""
    db = get_db()
    
    url_data = await db.urls.find_one({"short_code": short_code, "is_active": True})
    
    if not url_data:
        raise HTTPException(status_code=404, detail="URL not found")
    
    # Check if URL has expired
    if url_data.get("expires_at") and url_data["expires_at"] < datetime.utcnow():
        raise HTTPException(status_code=410, detail="This link has expired")
    
    # Check password protection
    if url_data.get("password"):
        # If no password provided, show password form
        if not password:
            return HTMLResponse(f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Password Protected Link - Linkify</title>
                <style>
                    body {{
                        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                        background: #0a0a0a;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                    }}
                    .container {{
                        background: #111111;
                        padding: 2rem;
                        border-radius: 10px;
                        box-shadow: 0 10px 25px rgba(0,0,0,0.3);
                        text-align: center;
                        border: 1px solid #2a2a2a;
                    }}
                    h2 {{
                        color: white;
                        margin-bottom: 1rem;
                    }}
                    p {{
                        color: #888;
                        margin-bottom: 1rem;
                    }}
                    input {{
                        padding: 12px;
                        width: 250px;
                        margin: 10px 0;
                        border: 1px solid #2a2a2a;
                        border-radius: 5px;
                        background: #1a1a1a;
                        color: white;
                    }}
                    button {{
                        padding: 12px 24px;
                        background: linear-gradient(135deg, #00d2ff 0%, #3a7bd5 100%);
                        color: white;
                        border: none;
                        border-radius: 5px;
                        cursor: pointer;
                        font-weight: 600;
                    }}
                    button:hover {{
                        transform: translateY(-2px);
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h2>🔒 Password Protected Link</h2>
                    <p>This link requires a password to access</p>
                    <form method="get">
                        <input type="password" name="password" placeholder="Enter password" autofocus>
                        <br>
                        <button type="submit">Unlock Link</button>
                    </form>
                </div>
            </body>
            </html>
            """)
        
        # Check password
        if password != url_data["password"]:
            raise HTTPException(status_code=401, detail="Incorrect password")
    
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