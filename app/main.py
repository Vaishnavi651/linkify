from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import RedirectResponse, HTMLResponse
from app.database import connect_to_mongo, close_mongo_connection, get_db
from app.auth import verify_password, hash_password, generate_session_token
from datetime import datetime, timedelta
import secrets

app = FastAPI()

# Simple in-memory database for testing (remove later)
users_db = {}
sessions_db = {}

@app.on_event("startup")
async def startup():
    print("Starting up...")
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown():
    await close_mongo_connection()

# Homepage
@app.get("/")
async def home():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Linkify - Login</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }
            .card {
                background: white;
                padding: 40px;
                border-radius: 10px;
                box-shadow: 0 10px 25px rgba(0,0,0,0.1);
                width: 350px;
            }
            h1 { text-align: center; color: #333; }
            input {
                width: 100%;
                padding: 10px;
                margin: 10px 0;
                border: 1px solid #ddd;
                border-radius: 5px;
            }
            button {
                width: 100%;
                padding: 10px;
                background: #667eea;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                margin-top: 10px;
            }
            .error { color: red; text-align: center; margin-top: 10px; display: none; }
            .tab { display: flex; gap: 10px; margin-bottom: 20px; }
            .tab button {
                flex: 1;
                background: #f0f0f0;
                color: #333;
                margin: 0;
            }
            .tab button.active { background: #667eea; color: white; }
            .form { display: none; }
            .form.active { display: block; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🔗 Linkify</h1>
            <div class="tab">
                <button id="loginTab" class="active">Login</button>
                <button id="signupTab">Sign Up</button>
            </div>
            <div id="loginForm" class="form active">
                <input type="email" id="loginEmail" placeholder="Email">
                <input type="password" id="loginPassword" placeholder="Password">
                <button onclick="login()">Login</button>
                <div id="loginError" class="error"></div>
            </div>
            <div id="signupForm" class="form">
                <input type="email" id="signupEmail" placeholder="Email">
                <input type="password" id="signupPassword" placeholder="Password">
                <button onclick="signup()">Sign Up</button>
                <div id="signupError" class="error"></div>
            </div>
        </div>
        <script>
            document.getElementById('loginTab').onclick = () => {
                document.getElementById('loginTab').classList.add('active');
                document.getElementById('signupTab').classList.remove('active');
                document.getElementById('loginForm').classList.add('active');
                document.getElementById('signupForm').classList.remove('active');
            };
            document.getElementById('signupTab').onclick = () => {
                document.getElementById('signupTab').classList.add('active');
                document.getElementById('loginTab').classList.remove('active');
                document.getElementById('signupForm').classList.add('active');
                document.getElementById('loginForm').classList.remove('active');
            };
            
            async function login() {
                const email = document.getElementById('loginEmail').value;
                const password = document.getElementById('loginPassword').value;
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
                    document.getElementById('loginError').innerText = data.detail;
                    document.getElementById('loginError').style.display = 'block';
                }
            }
            
            async function signup() {
                const email = document.getElementById('signupEmail').value;
                const password = document.getElementById('signupPassword').value;
                const response = await fetch('/api/signup', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({email, password})
                });
                const data = await response.json();
                if (response.ok) {
                    localStorage.setItem('token', data.token);
                    window.location.href = '/dashboard?token=' + data.token;
                } else {
                    document.getElementById('signupError').innerText = data.detail;
                    document.getElementById('signupError').style.display = 'block';
                }
            }
        </script>
    </body>
    </html>
    """)

# Dashboard
@app.get("/dashboard")
async def dashboard(token: str = None):
    if not token:
        return HTMLResponse("<h1>Not logged in</h1><a href='/'>Go back</a>")
    
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dashboard</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 20px;
                min-height: 100vh;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
                background: white;
                border-radius: 10px;
                padding: 20px;
            }}
            h1 {{ color: #333; }}
            input {{ padding: 10px; width: 70%; margin-right: 10px; }}
            button {{ padding: 10px 20px; background: #667eea; color: white; border: none; border-radius: 5px; cursor: pointer; }}
            .result {{ margin-top: 20px; padding: 10px; background: #f0f0f0; border-radius: 5px; display: none; }}
            .logout {{ float: right; }}
            .logout a {{ color: #667eea; text-decoration: none; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logout"><a href="/logout">Logout</a></div>
            <h1>🔗 Linkify Dashboard</h1>
            <p>Welcome! Your token: <code>{token[:30]}...</code></p>
            
            <h3>Create Short URL</h3>
            <input type="url" id="url" placeholder="https://example.com/long-url">
            <button onclick="shorten()">Shorten URL</button>
            <div id="result" class="result"></div>
        </div>
        
        <script>
            const token = '{token}';
            
            async function shorten() {{
                const longUrl = document.getElementById('url').value;
                const response = await fetch('/shorten', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token}},
                    body: JSON.stringify({{long_url: longUrl}})
                }});
                const data = await response.json();
                if (response.ok) {{
                    const resultDiv = document.getElementById('result');
                    resultDiv.innerHTML = `✅ Short URL: <a href="${{data.short_url}}" target="_blank">${{data.short_url}}</a>`;
                    resultDiv.style.display = 'block';
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
    
    token = generate_session_token()
    session = {"user_id": str(result.inserted_id), "token": token, "created_at": datetime.utcnow(), "expires_at": datetime.utcnow() + timedelta(days=30)}
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
    
    import random
    import string
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