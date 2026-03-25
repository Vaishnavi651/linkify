from fastapi import FastAPI, Request, HTTPException, Response, Cookie, Header
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app import schemas, utils, models
from app.database import connect_to_mongo, close_mongo_connection, get_db
from app.config import settings
from app.qrcode import generate_qr_code
from app.auth import hash_password, verify_password, generate_session_token
from datetime import datetime, timedelta

# Create FastAPI app
app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

# Mount static files (CSS, JS)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Set up templates
templates = Jinja2Templates(directory="app/templates")

# ============ DATABASE CONNECTION ============

@app.on_event("startup")
async def startup_event():
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown_event():
    await close_mongo_connection()

# ============ AUTH FUNCTIONS ============

async def get_current_user_from_token(token: str):
    """Get current user from session token"""
    if not token:
        return None
    
    db = get_db()
    session = await db.sessions.find_one({"token": token})
    if not session or session["expires_at"] < datetime.utcnow():
        return None
    
    user = await db.users.find_one({"_id": session["user_id"]})
    return user

# ============ MAIN PAGES ============

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the login/signup page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, token: str = None):
    """Dashboard page - shows user's URLs"""
    db = get_db()
    
    # Get token from query parameter or header
    if not token:
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
    
    user = await get_current_user_from_token(token)
    
    if not user:
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Not Authorized</title>
            <script>
                localStorage.removeItem('token');
                window.location.href = '/';
            </script>
        </head>
        <body>Redirecting...</body>
        </html>
        """, status_code=401)
    
    user_id = str(user["_id"])
    urls = await db.urls.find({"user_id": user_id}).sort("created_at", -1).to_list(length=100)
    
    urls_html = ""
    for url in urls:
        qr_link = f"/qr/{url['short_code']}"
        
        urls_html += f"""
        <div class="url-row" id="row-{url['short_code']}">
            <div class="short-url-col">
                <a href="/{url['short_code']}" target="_blank" class="short-url-link">
                    {settings.BASE_URL}/{url['short_code']}
                </a>
                <div class="url-actions">
                    <a href="{qr_link}" target="_blank" class="action-btn qr-btn">📱 QR Code</a>
                    <button onclick="deleteURL('{url['short_code']}')" class="action-btn delete-btn">🗑️ Delete</button>
                </div>
            </div>
            <div class="long-url">{url['long_url'][:60]}{'...' if len(url['long_url']) > 60 else ''}</div>
            <div class="clicks-count">👁️ {url.get('clicks', 0)} clicks</div>
            <div class="created-date">📅 {url['created_at'].strftime('%Y-%m-%d')}</div>
        </div>
        """
    
    if not urls:
        urls_html = '<div class="empty-state"><div class="empty-state-icon">🔗</div><h3>No URLs yet</h3><p>Create your first short URL below!</p></div>'
    
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
                <div class="logo"><span class="logo-icon">🔗</span><span class="logo-text">Linkify</span></div>
                <div class="nav-links">
                    <a href="/dashboard" class="nav-link active">Dashboard</a>
                    <div class="dropdown"><button class="dropbtn">Features ▼</button>
                        <div class="dropdown-content">
                            <a href="/feature/custom-code">✨ Custom Short Code</a>
                            <a href="/feature/qr-code">📱 QR Code</a>
                            <a href="/feature/expiration">⏰ URL Expiration</a>
                            <a href="/feature/password">🔒 Password Protection</a>
                        </div>
                    </div>
                    <a href="/about" class="nav-link">About</a>
                    <div class="user-info"><span class="user-email">{user['email']}</span><button onclick="logout()" class="logout-btn">Logout</button></div>
                </div>
            </div>
        </nav>

        <div class="dashboard-container">
            <div class="dashboard-header">
                <h1>📊 Your URLs</h1>
                <p>Track and manage all your shortened links</p>
            </div>

            <div class="shortener-card" style="margin-bottom: 2rem;">
                <div class="card-header"><h2>Create New Short URL</h2><p>Paste your long URL and get a short link</p></div>
                <div class="url-input-group">
                    <input type="url" id="longUrl" placeholder="https://example.com/very/long/url" class="url-input">
                    <button id="shortenBtn" class="shorten-btn">Shorten URL ⚡</button>
                </div>
                <div class="optional-fields" style="display: flex; gap: 1rem; margin-top: 1rem;">
                    <input type="text" id="customCode" placeholder="Custom code (optional)" class="url-input" style="flex:1">
                    <input type="number" id="expiresDays" placeholder="Expires in days" class="url-input" style="flex:1">
                    <input type="password" id="password" placeholder="Password (optional)" class="url-input" style="flex:1">
                </div>
                <div id="shortenResult" style="display: none; margin-top: 1rem; padding: 1rem; background: #1a1a1a; border-radius: 8px;">
                    <p>✅ <strong>Your short URL is ready!</strong></p>
                    <code id="shortUrlResult" style="color: #00d2ff;"></code>
                    <button onclick="copyShortUrl()" class="copy-btn" style="margin-left: 1rem;">📋 Copy</button>
                </div>
                <div id="shortenError" style="display: none; margin-top: 1rem; padding: 1rem; background: rgba(255,0,0,0.1); border-radius: 8px; color: #ff8888;"></div>
            </div>

            <div class="urls-table">
                <div class="table-header"><div>Short URL</div><div>Original URL</div><div>Clicks</div><div>Created</div></div>
                {urls_html}
            </div>
        </div>

        <footer class="footer"><div class="footer-container"><p>&copy; 2026 Linkify - Make your links shorter and smarter</p></div></footer>

        <script>
        const token = localStorage.getItem('token');
        if (!token) {{
            window.location.href = '/';
        }}

        async function deleteURL(shortCode) {{
            if (confirm('Delete this URL?')) {{
                const response = await fetch(`/delete/${{shortCode}}`, {{
                    method: 'DELETE',
                    headers: {{'Authorization': `Bearer ${{token}}`}}
                }});
                if (response.ok) location.reload();
            }}
        }}

        document.getElementById('shortenBtn').addEventListener('click', async () => {{
            const longUrl = document.getElementById('longUrl').value;
            const customCode = document.getElementById('customCode').value;
            const expiresDays = document.getElementById('expiresDays').value;
            const password = document.getElementById('password').value;
            
            if (!longUrl) {{
                document.getElementById('shortenError').innerHTML = 'Please enter a URL';
                document.getElementById('shortenError').style.display = 'block';
                return;
            }}
            
            const body = {{long_url: longUrl}};
            if (customCode) body.custom_code = customCode;
            if (expiresDays) body.expires_days = parseInt(expiresDays);
            if (password) body.password = password;
            
            const response = await fetch('/shorten', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json', 'Authorization': `Bearer ${{token}}`}},
                body: JSON.stringify(body)
            }});
            const data = await response.json();
            if (response.ok) {{
                document.getElementById('shortUrlResult').innerHTML = data.short_url;
                document.getElementById('shortenResult').style.display = 'block';
                document.getElementById('longUrl').value = '';
                document.getElementById('customCode').value = '';
                document.getElementById('expiresDays').value = '';
                document.getElementById('password').value = '';
                setTimeout(() => location.reload(), 1500);
            }} else {{
                document.getElementById('shortenError').innerHTML = data.detail || 'Failed';
                document.getElementById('shortenError').style.display = 'block';
            }}
        }});

        function copyShortUrl() {{
            navigator.clipboard.writeText(document.getElementById('shortUrlResult').innerHTML);
            alert('✅ Copied!');
        }}

        function logout() {{
            localStorage.removeItem('token');
            window.location.href = '/';
        }}
        </script>
    </body>
    </html>
    """)

# ============ FEATURE PAGES ============

@app.get("/feature/custom-code", response_class=HTMLResponse)
async def custom_code_page(request: Request):
    return templates.TemplateResponse("feature_custom_code.html", {"request": request})

@app.get("/feature/qr-code", response_class=HTMLResponse)
async def qr_code_page(request: Request):
    return templates.TemplateResponse("feature_qr_code.html", {"request": request})

@app.get("/feature/expiration", response_class=HTMLResponse)
async def expiration_page(request: Request):
    return templates.TemplateResponse("feature_expiration.html", {"request": request})

@app.get("/feature/password", response_class=HTMLResponse)
async def password_page(request: Request):
    return templates.TemplateResponse("feature_password.html", {"request": request})

@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    return HTMLResponse("""
    <!DOCTYPE html>
    <html><head><title>About</title><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/static/css/style.css"></head>
    <body><nav class="navbar"><div class="nav-container"><div class="logo"><span class="logo-icon">🔗</span><span class="logo-text">Linkify</span></div>
    <div class="nav-links"><a href="/dashboard" class="nav-link">Dashboard</a><div class="dropdown"><button class="dropbtn">Features ▼</button>
    <div class="dropdown-content"><a href="/feature/custom-code">✨ Custom Short Code</a><a href="/feature/qr-code">📱 QR Code</a>
    <a href="/feature/expiration">⏰ URL Expiration</a><a href="/feature/password">🔒 Password Protection</a></div></div>
    <a href="/about" class="nav-link active">About</a><button onclick="logout()" class="logout-btn">Logout</button></div></div></nav>
    <div class="about-page"><div class="about-header"><h1>About Linkify</h1><p>Professional URL Shortener</p></div>
    <div class="about-card"><h2>🚀 What is Linkify?</h2><p>Linkify helps you create short, memorable links that you can share anywhere.</p></div>
    <div class="about-card"><h2>✨ Features</h2><ul><li>✨ Custom Short Codes</li><li>📱 QR Code Generation</li><li>⏰ URL Expiration</li><li>🔒 Password Protection</li><li>📊 Analytics Dashboard</li></ul></div></div>
    <footer class="footer"><div class="footer-container"><p>&copy; 2026 Linkify</p></div></footer>
    <script>function logout(){localStorage.removeItem('token');window.location.href='/';}</script>
    </body></html>
    """)

# ============ AUTH API ============

@app.post("/api/signup")
async def signup(user_data: schemas.UserCreate):
    db = get_db()
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    password_hash = hash_password(user_data.password)
    user = {"email": user_data.email, "password_hash": password_hash, "created_at": datetime.utcnow(), "is_active": True}
    result = await db.users.insert_one(user)
    user_id = str(result.inserted_id)
    
    token = generate_session_token()
    session = {"user_id": user_id, "token": token, "created_at": datetime.utcnow(), "expires_at": datetime.utcnow() + timedelta(days=30)}
    await db.sessions.insert_one(session)
    
    return {"message": "User created successfully", "token": token}

@app.post("/api/login")
async def login(user_data: schemas.UserLogin):
    db = get_db()
    user = await db.users.find_one({"email": user_data.email})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_password(user_data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = generate_session_token()
    session = {"user_id": str(user["_id"]), "token": token, "created_at": datetime.utcnow(), "expires_at": datetime.utcnow() + timedelta(days=30)}
    await db.sessions.insert_one(session)
    
    return {"message": "Login successful", "token": token}

# ============ URL API ============

@app.post("/shorten")
async def create_short_url(url_data: schemas.URLCreate, authorization: str = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else None
    user = await get_current_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user_id = str(user["_id"])
    
    if url_data.custom_code:
        short_code = url_data.custom_code
        existing = await get_db().urls.find_one({"short_code": short_code})
        if existing:
            raise HTTPException(status_code=400, detail="Custom code already taken")
    else:
        short_code = utils.generate_random_code()
        existing = await get_db().urls.find_one({"short_code": short_code})
        while existing:
            short_code = utils.generate_random_code()
            existing = await get_db().urls.find_one({"short_code": short_code})
    
    url_doc = models.url_document(short_code, str(url_data.long_url), user_id, url_data.custom_code, url_data.expires_days, url_data.password)
    await get_db().urls.insert_one(url_doc)
    
    return {"short_code": short_code, "short_url": f"{settings.BASE_URL}/{short_code}", "long_url": str(url_data.long_url), "created_at": url_doc["created_at"], "clicks": 0}

@app.delete("/delete/{short_code}")
async def delete_url(short_code: str, authorization: str = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else None
    user = await get_current_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    db = get_db()
    url_data = await db.urls.find_one({"short_code": short_code})
    if not url_data:
        raise HTTPException(status_code=404, detail="URL not found")
    if url_data.get("user_id") != str(user["_id"]):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    await db.urls.delete_one({"short_code": short_code})
    return {"message": "Deleted"}

@app.post("/generate-qr")
async def generate_qr_code_api(data: dict):
    url = data.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    qr_img = generate_qr_code(url)
    return {"qr_code": f"data:image/png;base64,{qr_img}"}

@app.get("/qr/{short_code}")
async def get_qr_code_page(short_code: str):
    db = get_db()
    url_data = await db.urls.find_one({"short_code": short_code})
    if not url_data:
        raise HTTPException(status_code=404, detail="URL not found")
    short_url = f"{settings.BASE_URL}/{short_code}"
    qr_img = generate_qr_code(short_url)
    return HTMLResponse(f"<html><body style='text-align:center;background:#0a0a0a;color:white;'><h1>QR Code</h1><img src='data:image/png;base64,{qr_img}'><p>{short_url}</p><a href='/dashboard'>Back</a></body></html>")

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/{short_code}")
async def redirect_to_url(short_code: str, request: Request, password: str = None):
    db = get_db()
    url_data = await db.urls.find_one({"short_code": short_code, "is_active": True})
    if not url_data:
        raise HTTPException(status_code=404, detail="URL not found")
    if url_data.get("expires_at") and url_data["expires_at"] < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Link expired")
    if url_data.get("password"):
        if not password:
            return HTMLResponse("""
            <html><body style="background:#0a0a0a;color:white;display:flex;justify-content:center;align-items:center;height:100vh;">
            <div style="background:#111;padding:2rem;border-radius:10px;"><h2>🔒 Password Protected</h2>
            <form method="get"><input type="password" name="password" placeholder="Password"><br><button type="submit">Unlock</button></form></div></body></html>
            """)
        if password != url_data["password"]:
            raise HTTPException(status_code=401, detail="Incorrect password")
    await db.urls.update_one({"short_code": short_code}, {"$inc": {"clicks": 1}})
    return RedirectResponse(url=url_data["long_url"])