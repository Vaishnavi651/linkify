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
import json

# Create FastAPI app
app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# ============ DATABASE CONNECTION ============

@app.on_event("startup")
async def startup_event():
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown_event():
    await close_mongo_connection()

# ============ AUTH FUNCTIONS ============

async def get_current_user(token: str = None):
    if not token:
        return None
    db = get_db()
    session = await db.sessions.find_one({"token": token})
    if not session or session["expires_at"] < datetime.utcnow():
        return None
    user = await db.users.find_one({"_id": session["user_id"]})
    return user

# ============ MAIN PAGES ============

@app.get("/")
async def home():
    with open("app/templates/index.html", "r") as f:
        content = f.read()
    return HTMLResponse(content)

@app.get("/dashboard")
async def dashboard(token: str = None):
    # Check token from query parameter
    if not token:
        token = None
    
    user = await get_current_user(token)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    db = get_db()
    user_id = str(user["_id"])
    urls = await db.urls.find({"user_id": user_id}).sort("created_at", -1).to_list(length=100)
    
    # Build URLs HTML
    urls_html = ""
    for url in urls:
        urls_html += f"""
        <tr>
            <td><a href="/{url['short_code']}" target="_blank">{settings.BASE_URL}/{url['short_code']}</a></td>
            <td>{url['long_url'][:50]}{'...' if len(url['long_url']) > 50 else ''}</td>
            <td><a href="/qr/{url['short_code']}" target="_blank">📱 QR</a></td>
            <td>{url.get('clicks', 0)}</td>
            <td><button onclick="deleteURL('{url['short_code']}')" style="background:red;color:white;border:none;padding:5px 10px;border-radius:5px;">Delete</button></td>
        </tr>
        """
    
    if not urls:
        urls_html = '<tr><td colspan="5" style="text-align:center">No URLs yet. Create your first one below!</td></tr>'
    
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dashboard - Linkify</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: system-ui, sans-serif;
                background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
                color: white;
                min-height: 100vh;
                padding: 20px;
            }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }}
            .logo {{ font-size: 28px; font-weight: bold; }}
            .logout-btn {{ background: rgba(255,255,255,0.2); padding: 8px 16px; border-radius: 8px; text-decoration: none; color: white; }}
            .card {{
                background: rgba(255,255,255,0.1);
                backdrop-filter: blur(10px);
                border-radius: 16px;
                padding: 24px;
                margin-bottom: 30px;
            }}
            input, button {{
                padding: 12px;
                border-radius: 8px;
                border: none;
                font-size: 14px;
            }}
            input {{
                background: rgba(255,255,255,0.1);
                color: white;
                border: 1px solid rgba(255,255,255,0.2);
                flex: 1;
            }}
            button {{
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                cursor: pointer;
                font-weight: bold;
            }}
            .url-form {{
                display: flex;
                gap: 10px;
                flex-wrap: wrap;
            }}
            .url-form input {{
                flex: 1;
                min-width: 200px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
            }}
            th, td {{
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid rgba(255,255,255,0.1);
            }}
            th {{
                background: rgba(255,255,255,0.05);
            }}
            a {{ color: #88aaff; text-decoration: none; }}
            .result {{
                margin-top: 15px;
                padding: 10px;
                background: rgba(0,255,0,0.1);
                border-radius: 8px;
                display: none;
            }}
            .error {{
                margin-top: 15px;
                padding: 10px;
                background: rgba(255,0,0,0.1);
                border-radius: 8px;
                display: none;
                color: #ff8888;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">🔗 Linkify</div>
                <a href="/logout" class="logout-btn">Logout</a>
            </div>
            
            <div class="card">
                <h2>Create New Short URL</h2>
                <div class="url-form">
                    <input type="url" id="longUrl" placeholder="https://example.com/your-long-url">
                    <input type="text" id="customCode" placeholder="Custom code (optional)">
                    <input type="number" id="expiresDays" placeholder="Expires in days">
                    <input type="password" id="password" placeholder="Password (optional)">
                    <button onclick="createShortUrl()">Shorten URL ⚡</button>
                </div>
                <div id="result" class="result"></div>
                <div id="error" class="error"></div>
            </div>
            
            <div class="card">
                <h2>Your URLs</h2>
                <table>
                    <thead>
                        <tr><th>Short URL</th><th>Original URL</th><th>QR</th><th>Clicks</th><th>Action</th></tr>
                    </thead>
                    <tbody id="urlsList">
                        {urls_html}
                    </tbody>
                </table>
            </div>
        </div>
        
        <script>
            const token = '{token}' || localStorage.getItem('token');
            if (!token) {{
                window.location.href = '/';
            }}
            
            async function createShortUrl() {{
                const longUrl = document.getElementById('longUrl').value;
                const customCode = document.getElementById('customCode').value;
                const expiresDays = document.getElementById('expiresDays').value;
                const password = document.getElementById('password').value;
                const resultDiv = document.getElementById('result');
                const errorDiv = document.getElementById('error');
                
                resultDiv.style.display = 'none';
                errorDiv.style.display = 'none';
                
                if (!longUrl) {{
                    errorDiv.innerHTML = 'Please enter a URL';
                    errorDiv.style.display = 'block';
                    return;
                }}
                
                const body = {{long_url: longUrl}};
                if (customCode) body.custom_code = customCode;
                if (expiresDays) body.expires_days = parseInt(expiresDays);
                if (password) body.password = password;
                
                try {{
                    const response = await fetch('/shorten', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token}},
                        body: JSON.stringify(body)
                    }});
                    const data = await response.json();
                    if (response.ok) {{
                        resultDiv.innerHTML = `✅ Short URL: <a href="${{data.short_url}}" target="_blank">${{data.short_url}}</a>`;
                        resultDiv.style.display = 'block';
                        setTimeout(() => location.reload(), 2000);
                    }} else {{
                        errorDiv.innerHTML = data.detail || 'Failed';
                        errorDiv.style.display = 'block';
                    }}
                }} catch(err) {{
                    errorDiv.innerHTML = 'Connection error';
                    errorDiv.style.display = 'block';
                }}
            }}
            
            async function deleteURL(shortCode) {{
                if (confirm('Delete this URL?')) {{
                    const response = await fetch(`/delete/${{shortCode}}`, {{
                        method: 'DELETE',
                        headers: {{'Authorization': 'Bearer ' + token}}
                    }});
                    if (response.ok) location.reload();
                }}
            }}
        </script>
    </body>
    </html>
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

@app.get("/logout")
async def logout():
    return RedirectResponse(url="/")

# ============ URL API ============

@app.post("/shorten")
async def create_short_url(url_data: schemas.URLCreate, authorization: str = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else None
    user = await get_current_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    db = get_db()
    user_id = str(user["_id"])
    
    if url_data.custom_code:
        short_code = url_data.custom_code
        existing = await db.urls.find_one({"short_code": short_code})
        if existing:
            raise HTTPException(status_code=400, detail="Custom code already taken")
    else:
        short_code = utils.generate_random_code()
        existing = await db.urls.find_one({"short_code": short_code})
        while existing:
            short_code = utils.generate_random_code()
            existing = await db.urls.find_one({"short_code": short_code})
    
    url_doc = models.url_document(short_code, str(url_data.long_url), user_id, url_data.custom_code, url_data.expires_days, url_data.password)
    await db.urls.insert_one(url_doc)
    
    return {"short_code": short_code, "short_url": f"{settings.BASE_URL}/{short_code}", "long_url": str(url_data.long_url), "created_at": url_doc["created_at"], "clicks": 0}

@app.delete("/delete/{short_code}")
async def delete_url(short_code: str, authorization: str = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else None
    user = await get_current_user(token)
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

@app.get("/qr/{short_code}")
async def get_qr(short_code: str):
    db = get_db()
    url_data = await db.urls.find_one({"short_code": short_code})
    if not url_data:
        raise HTTPException(status_code=404)
    short_url = f"{settings.BASE_URL}/{short_code}"
    qr_img = generate_qr_code(short_url)
    return HTMLResponse(f"<html><body style='text-align:center;background:#0a0a0a;color:white;'><h1>QR Code</h1><img src='data:image/png;base64,{qr_img}'><p>{short_url}</p><a href='/dashboard'>Back</a></body></html>")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/{short_code}")
async def redirect_to_url(short_code: str, password: str = None):
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