from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from app.database import connect_to_mongo, close_mongo_connection, get_db
from datetime import datetime, timedelta
import random
import string

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")

BASE_URL = "https://linkify-1nnz.onrender.com"

@app.on_event("startup")
async def startup_event():
    await connect_to_mongo()
    print("Connected to MongoDB")

@app.on_event("shutdown")
async def shutdown_event():
    await close_mongo_connection()
    print("Disconnected from MongoDB")

# Helper function
def generate_random_code(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# Homepage
@app.get("/")
async def home():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Linkify - URL Shortener</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: system-ui, -apple-system, sans-serif;
                background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
            }
            .container {
                background: rgba(255,255,255,0.1);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 40px;
                width: 100%;
                max-width: 500px;
                text-align: center;
                border: 1px solid rgba(255,255,255,0.2);
            }
            h1 { color: white; font-size: 48px; margin-bottom: 10px; }
            .subtitle { color: rgba(255,255,255,0.7); margin-bottom: 30px; }
            input {
                width: 100%;
                padding: 15px;
                background: rgba(255,255,255,0.1);
                border: 1px solid rgba(255,255,255,0.2);
                border-radius: 12px;
                color: white;
                font-size: 16px;
                margin-bottom: 15px;
            }
            button {
                width: 100%;
                padding: 15px;
                background: linear-gradient(135deg, #667eea, #764ba2);
                border: none;
                border-radius: 12px;
                color: white;
                font-size: 18px;
                font-weight: bold;
                cursor: pointer;
            }
            .result {
                margin-top: 20px;
                padding: 15px;
                background: rgba(0,255,0,0.1);
                border-radius: 12px;
                display: none;
            }
            .result a { color: #88ff88; }
            .error {
                margin-top: 20px;
                padding: 15px;
                background: rgba(255,0,0,0.1);
                border-radius: 12px;
                color: #ff8888;
                display: none;
            }
            .links {
                margin-top: 20px;
                display: flex;
                gap: 15px;
                justify-content: center;
            }
            .links a {
                color: rgba(255,255,255,0.7);
                text-decoration: none;
            }
            .links a:hover { color: white; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔗 Linkify</h1>
            <div class="subtitle">Shorten, Share, Track</div>
            
            <input type="url" id="urlInput" placeholder="https://example.com/your-long-url">
            <button onclick="shorten()">Shorten URL ⚡</button>
            
            <div id="result" class="result"></div>
            <div id="error" class="error"></div>
            
            <div class="links">
                <a href="/dashboard">📊 Dashboard</a>
            </div>
        </div>
        
        <script>
            async function shorten() {
                const url = document.getElementById('urlInput').value;
                const resultDiv = document.getElementById('result');
                const errorDiv = document.getElementById('error');
                resultDiv.style.display = 'none';
                errorDiv.style.display = 'none';
                
                if (!url) {
                    errorDiv.innerHTML = 'Please enter a URL';
                    errorDiv.style.display = 'block';
                    return;
                }
                
                try {
                    const response = await fetch('/shorten', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({long_url: url})
                    });
                    const data = await response.json();
                    if (response.ok) {
                        resultDiv.innerHTML = `✅ Short URL: <a href="${data.short_url}" target="_blank">${data.short_url}</a><br><button onclick="copyToClipboard('${data.short_url}')" style="margin-top:10px; padding:8px 16px; background:#667eea; border:none; border-radius:8px; color:white; cursor:pointer;">📋 Copy</button>`;
                        resultDiv.style.display = 'block';
                        document.getElementById('urlInput').value = '';
                    } else {
                        errorDiv.innerHTML = data.detail || 'Failed to shorten URL';
                        errorDiv.style.display = 'block';
                    }
                } catch(err) {
                    errorDiv.innerHTML = 'Connection error';
                    errorDiv.style.display = 'block';
                }
            }
            
            function copyToClipboard(text) {
                navigator.clipboard.writeText(text);
                alert('✅ Copied to clipboard!');
            }
        </script>
    </body>
    </html>
    """)

# Dashboard
@app.get("/dashboard")
async def dashboard():
    db = get_db()
    urls = await db.urls.find().sort("created_at", -1).to_list(length=100)
    
    urls_html = ""
    for url in urls:
        urls_html += f"""
        <div style="border-bottom:1px solid #eee; padding:15px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <a href="/{url['short_code']}" target="_blank" style="color:#667eea; font-weight:bold;">
                        {BASE_URL}/{url['short_code']}
                    </a>
                    <div style="color:#888; font-size:12px; margin-top:5px;">
                        {url['long_url'][:80]}{'...' if len(url['long_url']) > 80 else ''}
                    </div>
                </div>
                <div style="text-align:right;">
                    <div>👁️ {url.get('clicks', 0)} clicks</div>
                    <div style="font-size:12px; color:#888;">{url['created_at'].strftime('%Y-%m-%d')}</div>
                    <button onclick="deleteURL('{url['short_code']}')" style="margin-top:5px; padding:5px 10px; background:#e74c3c; color:white; border:none; border-radius:5px; cursor:pointer;">Delete</button>
                </div>
            </div>
        </div>
        """
    
    if not urls:
        urls_html = '<div style="text-align:center; padding:40px; color:#888;">No URLs yet. Create your first one!</div>'
    
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
                min-height: 100vh;
                padding: 20px;
            }}
            .container {{
                max-width: 900px;
                margin: 0 auto;
            }}
            .header {{
                background: rgba(255,255,255,0.1);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 20px 30px;
                margin-bottom: 20px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .logo {{
                font-size: 24px;
                font-weight: bold;
                color: white;
            }}
            .nav a {{
                color: white;
                text-decoration: none;
                margin-left: 20px;
                padding: 8px 16px;
                border-radius: 8px;
            }}
            .nav a:hover {{ background: rgba(255,255,255,0.2); }}
            .card {{
                background: rgba(255,255,255,0.1);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 30px;
                margin-bottom: 20px;
            }}
            h2 {{ color: white; margin-bottom: 20px; }}
            .url-form {{
                display: flex;
                gap: 10px;
                margin-bottom: 20px;
            }}
            .url-form input {{
                flex: 1;
                padding: 12px;
                background: rgba(255,255,255,0.1);
                border: 1px solid rgba(255,255,255,0.2);
                border-radius: 10px;
                color: white;
            }}
            .url-form button {{
                padding: 12px 24px;
                background: linear-gradient(135deg, #667eea, #764ba2);
                border: none;
                border-radius: 10px;
                color: white;
                cursor: pointer;
            }}
            .urls-list {{
                background: rgba(255,255,255,0.05);
                border-radius: 16px;
                overflow: hidden;
            }}
            .result {{
                margin-top: 15px;
                padding: 12px;
                background: rgba(0,255,0,0.1);
                border-radius: 10px;
                display: none;
                color: #88ff88;
            }}
            .error {{
                margin-top: 15px;
                padding: 12px;
                background: rgba(255,0,0,0.1);
                border-radius: 10px;
                display: none;
                color: #ff8888;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">🔗 Linkify</div>
                <div class="nav">
                    <a href="/">Home</a>
                    <a href="/dashboard">Dashboard</a>
                </div>
            </div>
            
            <div class="card">
                <h2>Create New Short URL</h2>
                <div class="url-form">
                    <input type="url" id="longUrl" placeholder="https://example.com/your-long-url">
                    <button onclick="createShortUrl()">Shorten URL ⚡</button>
                </div>
                <div id="result" class="result"></div>
                <div id="error" class="error"></div>
            </div>
            
            <div class="card">
                <h2>All Short URLs</h2>
                <div class="urls-list">
                    {urls_html}
                </div>
            </div>
        </div>
        
        <script>
            async function createShortUrl() {{
                const longUrl = document.getElementById('longUrl').value;
                const resultDiv = document.getElementById('result');
                const errorDiv = document.getElementById('error');
                resultDiv.style.display = 'none';
                errorDiv.style.display = 'none';
                
                if (!longUrl) {{
                    errorDiv.innerHTML = 'Please enter a URL';
                    errorDiv.style.display = 'block';
                    return;
                }}
                
                const response = await fetch('/shorten', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{long_url: longUrl}})
                }});
                const data = await response.json();
                if (response.ok) {{
                    resultDiv.innerHTML = `✅ Short URL created: <a href="${{data.short_url}}" target="_blank">${{data.short_url}}</a>`;
                    resultDiv.style.display = 'block';
                    document.getElementById('longUrl').value = '';
                    setTimeout(() => location.reload(), 1500);
                }} else {{
                    errorDiv.innerHTML = data.detail || 'Failed to create URL';
                    errorDiv.style.display = 'block';
                }}
            }}
            
            async function deleteURL(shortCode) {{
                if (confirm('Delete this URL?')) {{
                    const response = await fetch(`/delete/${{shortCode}}`, {{ method: 'DELETE' }});
                    if (response.ok) location.reload();
                }}
            }}
        </script>
    </body>
    </html>
    """)

# API Endpoints
@app.post("/shorten")
async def shorten(data: dict):
    db = get_db()
    long_url = data.get("long_url")
    
    if not long_url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    short_code = generate_random_code()
    existing = await db.urls.find_one({"short_code": short_code})
    while existing:
        short_code = generate_random_code()
        existing = await db.urls.find_one({"short_code": short_code})
    
    url_doc = {
        "short_code": short_code,
        "long_url": long_url,
        "created_at": datetime.utcnow(),
        "clicks": 0,
        "is_active": True
    }
    await db.urls.insert_one(url_doc)
    
    return {"short_url": f"{BASE_URL}/{short_code}"}

@app.delete("/delete/{short_code}")
async def delete_url(short_code: str):
    db = get_db()
    await db.urls.delete_one({"short_code": short_code})
    return {"message": "Deleted"}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/{short_code}")
async def redirect_url(short_code: str):
    db = get_db()
    url = await db.urls.find_one({"short_code": short_code, "is_active": True})
    if not url:
        return HTMLResponse("URL not found", status_code=404)
    await db.urls.update_one({"short_code": short_code}, {"$inc": {"clicks": 1}})
    return RedirectResponse(url=url["long_url"])