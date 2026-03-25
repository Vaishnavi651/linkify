from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import RedirectResponse, HTMLResponse
from app.database import connect_to_mongo, close_mongo_connection, get_db
from app.auth import verify_password, hash_password, generate_session_token
from datetime import datetime, timedelta
import random
import string
from bson import ObjectId

app = FastAPI()

@app.on_event("startup")
async def startup():
    print("Starting up...")
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown():
    await close_mongo_connection()

# Helper to convert ObjectId to string
def str_id(obj_id):
    return str(obj_id)

# Homepage
@app.get("/")
async def home():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Linkify - Login</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: system-ui, -apple-system, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
            }
            .card {
                background: white;
                border-radius: 20px;
                padding: 40px;
                width: 100%;
                max-width: 400px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            }
            h1 { text-align: center; color: #333; margin-bottom: 10px; font-size: 32px; }
            .subtitle { text-align: center; color: #666; margin-bottom: 30px; font-size: 14px; }
            .tabs { display: flex; gap: 10px; margin-bottom: 30px; }
            .tab {
                flex: 1;
                padding: 12px;
                background: #f0f0f0;
                border: none;
                border-radius: 10px;
                cursor: pointer;
                font-size: 16px;
                font-weight: 600;
            }
            .tab.active { background: linear-gradient(135deg, #667eea, #764ba2); color: white; }
            .form { display: none; }
            .form.active { display: block; }
            input {
                width: 100%;
                padding: 12px;
                margin: 10px 0;
                border: 1px solid #ddd;
                border-radius: 8px;
                font-size: 14px;
            }
            button {
                width: 100%;
                padding: 12px;
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                margin-top: 20px;
            }
            .error { color: #e74c3c; text-align: center; margin-top: 15px; font-size: 14px; display: none; }
            .success { color: #27ae60; text-align: center; margin-top: 15px; font-size: 14px; display: none; }
            .features {
                display: flex;
                justify-content: space-between;
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #eee;
            }
            .feature { text-align: center; font-size: 12px; color: #888; }
            .feature span { font-size: 24px; display: block; margin-bottom: 5px; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🔗 Linkify</h1>
            <div class="subtitle">Shorten, Share, Track</div>
            
            <div class="tabs">
                <button class="tab active" id="loginTab">Login</button>
                <button class="tab" id="signupTab">Sign Up</button>
            </div>
            
            <div id="loginForm" class="form active">
                <input type="email" id="loginEmail" placeholder="Email address">
                <input type="password" id="loginPassword" placeholder="Password">
                <button onclick="login()">Login →</button>
                <div id="loginError" class="error"></div>
            </div>
            
            <div id="signupForm" class="form">
                <input type="email" id="signupEmail" placeholder="Email address">
                <input type="password" id="signupPassword" placeholder="Password (min 6 characters)">
                <button onclick="signup()">Create Account →</button>
                <div id="signupError" class="error"></div>
                <div id="signupSuccess" class="success"></div>
            </div>
            
            <div class="features">
                <div class="feature"><span>✨</span> Custom Codes</div>
                <div class="feature"><span>📱</span> QR Codes</div>
                <div class="feature"><span>🔒</span> Password Protect</div>
                <div class="feature"><span>📊</span> Analytics</div>
            </div>
        </div>
        
        <script>
            function setActiveTab(tab) {
                if (tab === 'login') {
                    document.getElementById('loginTab').classList.add('active');
                    document.getElementById('signupTab').classList.remove('active');
                    document.getElementById('loginForm').classList.add('active');
                    document.getElementById('signupForm').classList.remove('active');
                } else {
                    document.getElementById('signupTab').classList.add('active');
                    document.getElementById('loginTab').classList.remove('active');
                    document.getElementById('signupForm').classList.add('active');
                    document.getElementById('loginForm').classList.remove('active');
                }
            }
            
            document.getElementById('loginTab').onclick = () => setActiveTab('login');
            document.getElementById('signupTab').onclick = () => setActiveTab('signup');
            
            async function login() {
                const email = document.getElementById('loginEmail').value;
                const password = document.getElementById('loginPassword').value;
                const errorDiv = document.getElementById('loginError');
                errorDiv.style.display = 'none';
                
                if (!email || !password) {
                    errorDiv.textContent = 'Please fill all fields';
                    errorDiv.style.display = 'block';
                    return;
                }
                
                try {
                    const response = await fetch('/api/login', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({email, password})
                    });
                    const data = await response.json();
                    
                    if (response.ok) {
                        localStorage.setItem('token', data.token);
                        window.location.href = '/dashboard?token=' + data.token;
                    } else {
                        errorDiv.textContent = data.detail || 'Login failed';
                        errorDiv.style.display = 'block';
                    }
                } catch (err) {
                    errorDiv.textContent = 'Connection error';
                    errorDiv.style.display = 'block';
                }
            }
            
            async function signup() {
                const email = document.getElementById('signupEmail').value;
                const password = document.getElementById('signupPassword').value;
                const errorDiv = document.getElementById('signupError');
                const successDiv = document.getElementById('signupSuccess');
                errorDiv.style.display = 'none';
                successDiv.style.display = 'none';
                
                if (!email || !password) {
                    errorDiv.textContent = 'Please fill all fields';
                    errorDiv.style.display = 'block';
                    return;
                }
                if (password.length < 6) {
                    errorDiv.textContent = 'Password must be at least 6 characters';
                    errorDiv.style.display = 'block';
                    return;
                }
                
                try {
                    const response = await fetch('/api/signup', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({email, password})
                    });
                    const data = await response.json();
                    
                    if (response.ok) {
                        successDiv.textContent = 'Account created! Logging you in...';
                        successDiv.style.display = 'block';
                        localStorage.setItem('token', data.token);
                        setTimeout(() => {
                            window.location.href = '/dashboard?token=' + data.token;
                        }, 1000);
                    } else {
                        errorDiv.textContent = data.detail || 'Signup failed';
                        errorDiv.style.display = 'block';
                    }
                } catch (err) {
                    errorDiv.textContent = 'Connection error';
                    errorDiv.style.display = 'block';
                }
            }
        </script>
    </body>
    </html>
    """)

# Dashboard Page
@app.get("/dashboard")
async def dashboard(token: str = None):
    if not token:
        return HTMLResponse("<h1>No token provided</h1><a href='/'>Go back</a>")
    
    print(f"Dashboard called with token: {token[:20]}...")
    
    db = get_db()
    session = await db.sessions.find_one({"token": token})
    
    if not session:
        print("Session not found")
        return HTMLResponse("<h1>Invalid session token</h1><a href='/'>Go back</a>")
    
    print(f"Session found: user_id = {session['user_id']}")
    
    # Convert user_id string to ObjectId for MongoDB query
    try:
        user_id_obj = ObjectId(session["user_id"])
    except:
        print(f"Invalid user_id format: {session['user_id']}")
        return HTMLResponse("<h1>Invalid user ID format</h1><a href='/'>Go back</a>")
    
    user = await db.users.find_one({"_id": user_id_obj})
    
    if not user:
        print(f"User not found with _id: {session['user_id']}")
        return HTMLResponse("<h1>User not found</h1><a href='/'>Go back</a>")
    
    print(f"User found: {user['email']}")
    
    # Get user's URLs
    urls = await db.urls.find({"user_id": session["user_id"]}).sort("created_at", -1).to_list(length=100)
    
    urls_html = ""
    for url in urls:
        urls_html += f"""
        <div style="border-bottom:1px solid #eee; padding:10px;">
            <a href="/{url['short_code']}" target="_blank" style="color:#667eea;">https://linkify-1nnz.onrender.com/{url['short_code']}</a>
            <span style="color:#888; margin-left:10px;">{url['long_url'][:50]}</span>
            <span style="float:right;">👁️ {url.get('clicks', 0)}</span>
        </div>
        """
    
    if not urls:
        urls_html = '<div style="padding:20px; text-align:center; color:#888;">No URLs yet. Create your first one below!</div>'
    
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dashboard - Linkify</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: system-ui, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
            }}
            .card {{
                background: white;
                border-radius: 20px;
                padding: 30px;
                margin-bottom: 20px;
                box-shadow: 0 10px 20px rgba(0,0,0,0.1);
            }}
            h1 {{ margin-bottom: 10px; }}
            .email {{ color: #667eea; margin-bottom: 20px; }}
            input {{
                padding: 12px;
                border: 1px solid #ddd;
                border-radius: 8px;
                width: 70%;
                margin-right: 10px;
            }}
            button {{
                padding: 12px 24px;
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                border: none;
                border-radius: 8px;
                cursor: pointer;
            }}
            .logout {{
                float: right;
                background: #e74c3c;
                padding: 8px 16px;
                border-radius: 8px;
                color: white;
                text-decoration: none;
            }}
            .result {{
                margin-top: 15px;
                padding: 12px;
                background: #e8f5e9;
                border-radius: 8px;
                display: none;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <a href="/logout" class="logout">Logout</a>
                <h1>🔗 Linkify Dashboard</h1>
                <p class="email">Welcome, <strong>{user['email']}</strong>!</p>
                
                <div style="margin: 20px 0;">
                    <input type="url" id="longUrl" placeholder="https://example.com/your-long-url">
                    <button onclick="shorten()">Shorten URL ⚡</button>
                </div>
                <div id="result" class="result"></div>
            </div>
            
            <div class="card">
                <h3>Your Short URLs</h3>
                <div style="margin-top: 15px;">
                    {urls_html}
                </div>
            </div>
        </div>
        
        <script>
            const token = '{token}';
            
            async function shorten() {{
                const longUrl = document.getElementById('longUrl').value;
                if (!longUrl) {{
                    alert('Please enter a URL');
                    return;
                }}
                
                const response = await fetch('/shorten', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token}},
                    body: JSON.stringify({{long_url: longUrl}})
                }});
                const data = await response.json();
                if (response.ok) {{
                    const resultDiv = document.getElementById('result');
                    resultDiv.innerHTML = `✅ Short URL created: <a href="${{data.short_url}}" target="_blank">${{data.short_url}}</a>`;
                    resultDiv.style.display = 'block';
                    setTimeout(() => location.reload(), 2000);
                }} else {{
                    alert(data.detail || 'Failed to shorten URL');
                }}
            }}
        </script>
    </body>
    </html>
    """)

# API Endpoints
@app.post("/api/signup")
async def signup(data: dict):
    db = get_db()
    email = data.get("email")
    password = data.get("password")
    
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    password_hash = hash_password(password)
    user = {"email": email, "password_hash": password_hash, "created_at": datetime.utcnow()}
    result = await db.users.insert_one(user)
    user_id = str(result.inserted_id)
    
    token = generate_session_token()
    session = {"user_id": user_id, "token": token, "created_at": datetime.utcnow(), "expires_at": datetime.utcnow() + timedelta(days=30)}
    await db.sessions.insert_one(session)
    
    return {"token": token}

@app.post("/api/login")
async def login(data: dict):
    db = get_db()
    email = data.get("email")
    password = data.get("password")
    
    user = await db.users.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = generate_session_token()
    session = {"user_id": str(user["_id"]), "token": token, "created_at": datetime.utcnow(), "expires_at": datetime.utcnow() + timedelta(days=30)}
    await db.sessions.insert_one(session)
    
    return {"token": token}

@app.post("/shorten")
async def shorten(data: dict, authorization: str = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else None
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    db = get_db()
    session = await db.sessions.find_one({"token": token})
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    short_code = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    
    url_doc = {
        "short_code": short_code,
        "long_url": data.get("long_url"),
        "user_id": session["user_id"],
        "created_at": datetime.utcnow(),
        "clicks": 0
    }
    await db.urls.insert_one(url_doc)
    
    return {"short_url": f"https://linkify-1nnz.onrender.com/{short_code}"}

@app.get("/logout")
async def logout():
    return RedirectResponse(url="/")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/{short_code}")
async def redirect(short_code: str):
    db = get_db()
    url = await db.urls.find_one({"short_code": short_code})
    if not url:
        return HTMLResponse("URL not found", status_code=404)
    await db.urls.update_one({"short_code": short_code}, {"$inc": {"clicks": 1}})
    return RedirectResponse(url=url["long_url"])