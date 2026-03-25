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

# ============ MAIN PAGES ============

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the homepage"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard page - shows all URLs"""
    db = get_db()
    
    urls = await db.urls.find().sort("created_at", -1).to_list(length=100)
    
    urls_html = ""
    for url in urls:
        qr_link = f"/qr/{url['short_code']}"
        delete_link = f"javascript:deleteURL('{url['short_code']}')"
        
        # Show expiration info if exists
        expires_info = ""
        expires_class = ""
        if url.get('expires_at'):
            expires_date = url['expires_at'].strftime('%Y-%m-%d')
            expires_info = f"📅 Expires: {expires_date}"
            expires_class = "has-expiry"
        
        # Show password info if exists
        password_info = ""
        password_class = ""
        if url.get('is_password_protected'):
            password_info = "🔒 Password Protected"
            password_class = "has-password"
        
        urls_html += f"""
        <div class="url-row" id="row-{url['short_code']}">
            <div class="short-url-col">
                <a href="/{url['short_code']}" target="_blank" class="short-url-link">
                    {settings.BASE_URL}/{url['short_code']}
                </a>
                <div class="url-actions">
                    <a href="{qr_link}" target="_blank" class="action-btn qr-btn" title="Generate QR Code">📱</a>
                    <button onclick="{delete_link}" class="action-btn delete-btn" title="Delete URL">🗑️</button>
                </div>
            </div>
            <div class="long-url" title="{url['long_url']}">
                {url['long_url'][:60]}{'...' if len(url['long_url']) > 60 else ''}
            </div>
            <div class="url-info">
                <span class="clicks-count">👁️ {url.get('clicks', 0)} clicks</span>
                {f'<span class="expiry-badge {expires_class}">{expires_info}</span>' if expires_info else ''}
                {f'<span class="password-badge {password_class}">{password_info}</span>' if password_info else ''}
            </div>
            <div class="created-date">📅 {url['created_at'].strftime('%Y-%m-%d %H:%M')}</div>
        </div>
        """
    
    if not urls:
        urls_html = """
        <div class="empty-state">
            <div class="empty-state-icon">🔗</div>
            <h3>No URLs yet</h3>
            <p>Create your first short URL on the homepage!</p>
            <a href="/" class="btn-primary">Go to Homepage</a>
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
                    <div class="dropdown">
                        <button class="dropbtn">Features ▼</button>
                        <div class="dropdown-content">
                            <a href="/custom-code">✨ Custom Short Codes</a>
                            <a href="/qr-code">📱 QR Code Generator</a>
                            <a href="/expiration">⏰ URL Expiration</a>
                            <a href="/password">🔒 Password Protection</a>
                        </div>
                    </div>
                    <a href="/about" class="nav-link">About</a>
                </div>
            </div>
        </nav>

        <div class="dashboard-container">
            <div class="dashboard-header">
                <h1>📊 Your URLs</h1>
                <p>Track and manage all your shortened links</p>
                <div class="legend">
                    <span class="legend-item">🔒 = Password protected</span>
                    <span class="legend-item">📅 = Has expiration date</span>
                    <span class="legend-item">👁️ = Total clicks</span>
                </div>
            </div>

            <div class="urls-table">
                <div class="table-header">
                    <div>Short URL</div>
                    <div>Original URL</div>
                    <div>Info</div>
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

        <script>
        async function deleteURL(shortCode) {{
            if (confirm('Are you sure you want to delete this URL? This action cannot be undone.')) {{
                try {{
                    const response = await fetch(`/delete/${{shortCode}}`, {{
                        method: 'DELETE'
                    }});
                    
                    if (response.ok) {{
                        document.getElementById(`row-${{shortCode}}`).remove();
                        alert('✅ URL deleted successfully!');
                        if (document.querySelectorAll('.url-row').length === 0) {{
                            location.reload();
                        }}
                    }} else {{
                        const data = await response.json();
                        alert(data.detail || 'Failed to delete URL');
                    }}
                }} catch (error) {{
                    alert('Error deleting URL');
                }}
            }}
        }}
        </script>
    </body>
    </html>
    """)

# ============ FEATURE PAGES ============

@app.get("/custom-code", response_class=HTMLResponse)
async def custom_code_page(request: Request):
    """Custom short codes feature page"""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Custom Short Codes - Linkify</title>
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
                    <a href="/dashboard" class="nav-link">Dashboard</a>
                    <div class="dropdown">
                        <button class="dropbtn active">Features ▼</button>
                        <div class="dropdown-content">
                            <a href="/custom-code" class="active">✨ Custom Short Codes</a>
                            <a href="/qr-code">📱 QR Code Generator</a>
                            <a href="/expiration">⏰ URL Expiration</a>
                            <a href="/password">🔒 Password Protection</a>
                        </div>
                    </div>
                    <a href="/about" class="nav-link">About</a>
                </div>
            </div>
        </nav>

        <div class="feature-page">
            <div class="feature-header">
                <h1>✨ Custom Short Codes</h1>
                <p>Create memorable, branded links that are easy to share</p>
            </div>

            <div class="feature-content">
                <div class="feature-card-large">
                    <h2>How it works</h2>
                    <p>Instead of random codes like <code>aB3xK9</code>, you can create custom short codes like:</p>
                    <div class="example-list">
                        <div class="example-item">
                            <span class="example-icon">🎯</span>
                            <code>linkify.onrender.com/mywebsite</code>
                        </div>
                        <div class="example-item">
                            <span class="example-icon">📱</span>
                            <code>linkify.onrender.com/instagram</code>
                        </div>
                        <div class="example-item">
                            <span class="example-icon">🛍️</span>
                            <code>linkify.onrender.com/sale2026</code>
                        </div>
                    </div>
                    <div class="feature-tip">
                        <strong>💡 Tip:</strong> Use letters, numbers, and hyphens only. Keep it short and memorable!
                    </div>
                    <a href="/" class="btn-primary">Try it now →</a>
                </div>
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

@app.get("/qr-code", response_class=HTMLResponse)
async def qr_code_page(request: Request):
    """QR Code feature page"""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>QR Code Generator - Linkify</title>
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
                    <a href="/dashboard" class="nav-link">Dashboard</a>
                    <div class="dropdown">
                        <button class="dropbtn active">Features ▼</button>
                        <div class="dropdown-content">
                            <a href="/custom-code">✨ Custom Short Codes</a>
                            <a href="/qr-code" class="active">📱 QR Code Generator</a>
                            <a href="/expiration">⏰ URL Expiration</a>
                            <a href="/password">🔒 Password Protection</a>
                        </div>
                    </div>
                    <a href="/about" class="nav-link">About</a>
                </div>
            </div>
        </nav>

        <div class="feature-page">
            <div class="feature-header">
                <h1>📱 QR Code Generator</h1>
                <p>Generate QR codes for any short URL - perfect for business cards, posters, and more!</p>
            </div>

            <div class="feature-content">
                <div class="feature-card-large">
                    <h2>How it works</h2>
                    <p>Every short URL you create automatically has a QR code. Just look for the 📱 icon in your dashboard!</p>
                    
                    <div class="qr-example">
                        <div class="qr-preview">
                            <div class="qr-placeholder">
                                <span>📱</span>
                                <p>Your QR code appears here</p>
                            </div>
                        </div>
                        <div class="qr-info">
                            <h3>Perfect for:</h3>
                            <ul>
                                <li>📇 Business cards</li>
                                <li>🖼️ Posters and flyers</li>
                                <li>📦 Product packaging</li>
                                <li>🎫 Event tickets</li>
                                <li>📱 Social media profiles</li>
                            </ul>
                        </div>
                    </div>
                    
                    <div class="feature-tip">
                        <strong>💡 Tip:</strong> Scan QR codes with your phone camera - no app needed!
                    </div>
                    <a href="/dashboard" class="btn-primary">View Dashboard →</a>
                </div>
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

@app.get("/expiration", response_class=HTMLResponse)
async def expiration_page(request: Request):
    """URL Expiration feature page"""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>URL Expiration - Linkify</title>
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
                    <a href="/dashboard" class="nav-link">Dashboard</a>
                    <div class="dropdown">
                        <button class="dropbtn active">Features ▼</button>
                        <div class="dropdown-content">
                            <a href="/custom-code">✨ Custom Short Codes</a>
                            <a href="/qr-code">📱 QR Code Generator</a>
                            <a href="/expiration" class="active">⏰ URL Expiration</a>
                            <a href="/password">🔒 Password Protection</a>
                        </div>
                    </div>
                    <a href="/about" class="nav-link">About</a>
                </div>
            </div>
        </nav>

        <div class="feature-page">
            <div class="feature-header">
                <h1>⏰ URL Expiration</h1>
                <p>Set links to automatically expire after a specific time</p>
            </div>

            <div class="feature-content">
                <div class="feature-card-large">
                    <h2>Perfect for:</h2>
                    <div class="use-cases-grid">
                        <div class="use-case">
                            <div class="use-icon">🎉</div>
                            <h3>Limited Offers</h3>
                            <p>Promotions that end on a specific date</p>
                        </div>
                        <div class="use-case">
                            <div class="use-icon">📧</div>
                            <h3>Email Campaigns</h3>
                            <p>Time-sensitive newsletters and updates</p>
                        </div>
                        <div class="use-case">
                            <div class="use-icon">🎟️</div>
                            <h3>Event Invitations</h3>
                            <p>Links that stop working after the event</p>
                        </div>
                        <div class="use-case">
                            <div class="use-icon">🔒</div>
                            <h3>Temporary Access</h3>
                            <p>Share sensitive links for a limited time</p>
                        </div>
                    </div>
                    
                    <div class="feature-tip">
                        <strong>💡 How to use:</strong> Simply enter the number of days in the "Expires in days" field when creating your short URL.
                    </div>
                    <a href="/" class="btn-primary">Create expiring link →</a>
                </div>
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

@app.get("/password", response_class=HTMLResponse)
async def password_page(request: Request):
    """Password Protection feature page"""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Password Protection - Linkify</title>
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
                    <a href="/dashboard" class="nav-link">Dashboard</a>
                    <div class="dropdown">
                        <button class="dropbtn active">Features ▼</button>
                        <div class="dropdown-content">
                            <a href="/custom-code">✨ Custom Short Codes</a>
                            <a href="/qr-code">📱 QR Code Generator</a>
                            <a href="/expiration">⏰ URL Expiration</a>
                            <a href="/password" class="active">🔒 Password Protection</a>
                        </div>
                    </div>
                    <a href="/about" class="nav-link">About</a>
                </div>
            </div>
        </nav>

        <div class="feature-page">
            <div class="feature-header">
                <h1>🔒 Password Protection</h1>
                <p>Keep your links secure with password protection</p>
            </div>

            <div class="feature-content">
                <div class="feature-card-large">
                    <h2>How it works</h2>
                    <p>When you create a short URL with a password, anyone who clicks it will need to enter the correct password before being redirected.</p>
                    
                    <div class="demo-box">
                        <h3>Example:</h3>
                        <div class="demo-step">
                            <span class="step-number">1</span>
                            <span>Create URL with password: <code>mysecret123</code></span>
                        </div>
                        <div class="demo-step">
                            <span class="step-number">2</span>
                            <span>Share the link: <code>linkify.onrender.com/private-link</code></span>
                        </div>
                        <div class="demo-step">
                            <span class="step-number">3</span>
                            <span>Recipient sees a password prompt 🔒</span>
                        </div>
                        <div class="demo-step">
                            <span class="step-number">4</span>
                            <span>Enter password → Redirected! ✅</span>
                        </div>
                    </div>
                    
                    <div class="feature-tip">
                        <strong>💡 Security Tip:</strong> Use strong passwords with a mix of letters, numbers, and special characters.
                    </div>
                    <a href="/" class="btn-primary">Create password-protected link →</a>
                </div>
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

@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    """About page"""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>About - Linkify</title>
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
                    <a href="/dashboard" class="nav-link">Dashboard</a>
                    <div class="dropdown">
                        <button class="dropbtn">Features ▼</button>
                        <div class="dropdown-content">
                            <a href="/custom-code">✨ Custom Short Codes</a>
                            <a href="/qr-code">📱 QR Code Generator</a>
                            <a href="/expiration">⏰ URL Expiration</a>
                            <a href="/password">🔒 Password Protection</a>
                        </div>
                    </div>
                    <a href="/about" class="nav-link active">About</a>
                </div>
            </div>
        </nav>

        <div class="about-page">
            <div class="about-header">
                <h1>About Linkify</h1>
                <p>Professional URL Shortener Service</p>
            </div>

            <div class="about-content">
                <div class="about-card">
                    <h2>🚀 What is Linkify?</h2>
                    <p>Linkify is a professional URL shortener that helps you create short, memorable links that you can share anywhere. Track clicks, analyze traffic, and optimize your content with our powerful features.</p>
                </div>

                <div class="about-card">
                    <h2>✨ Features</h2>
                    <ul class="feature-list">
                        <li>🔗 <strong>Custom Short Codes</strong> - Create branded, memorable links</li>
                        <li>📱 <strong>QR Code Generation</strong> - Generate QR codes for any short URL</li>
                        <li>⏰ <strong>URL Expiration</strong> - Links that auto-expire after a set time</li>
                        <li>🔒 <strong>Password Protection</strong> - Keep sensitive links secure</li>
                        <li>📊 <strong>Analytics Dashboard</strong> - Track clicks and performance</li>
                        <li>⚡ <strong>Lightning Fast</strong> - Sub-50ms redirect latency</li>
                    </ul>
                </div>

                <div class="about-card">
                    <h2>🛠️ Built With</h2>
                    <div class="tech-stack">
                        <span class="tech-badge">FastAPI</span>
                        <span class="tech-badge">MongoDB</span>
                        <span class="tech-badge">Python</span>
                        <span class="tech-badge">HTML5/CSS3</span>
                        <span class="tech-badge">JavaScript</span>
                        <span class="tech-badge">Render</span>
                    </div>
                </div>

                <div class="about-card">
                    <h2>📧 Contact</h2>
                    <p>Have questions or feedback? Reach out!</p>
                    <p>Email: <a href="mailto:vaishnavi@linkify.com">vaishnavi@linkify.com</a></p>
                    <p>GitHub: <a href="https://github.com/Vaishnavi651/linkify" target="_blank">github.com/Vaishnavi651/linkify</a></p>
                </div>
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

# ============ API ENDPOINTS ============

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
            .button-group {{
                margin-top: 20px;
            }}
            .download-btn {{
                background: #10b981;
                margin-left: 10px;
            }}
        </style>
    </head>
    <body>
        <h1>📱 QR Code for your link</h1>
        <div class="qr-container">
            <img src="data:image/png;base64,{qr_img}" alt="QR Code" id="qr-image">
        </div>
        <div class="info">
            <p class="short-url">🔗 {short_url}</p>
            <p>Scan this QR code to visit the link instantly!</p>
            <div class="button-group">
                <a href="/dashboard">← Back to Dashboard</a>
                <a href="/" class="download-btn">Home</a>
            </div>
        </div>
        <script>
            // Add download functionality
            const qrImage = document.getElementById('qr-image');
            const downloadBtn = document.createElement('a');
            downloadBtn.href = qrImage.src;
            downloadBtn.download = 'qrcode.png';
            downloadBtn.textContent = '📥 Download QR Code';
            downloadBtn.className = 'download-btn';
            downloadBtn.style.marginLeft = '10px';
            document.querySelector('.button-group').appendChild(downloadBtn);
        </script>
    </body>
    </html>
    """)

@app.get("/health")
async def health_check():
    """Health check endpoint for uptime monitoring"""
    return {"status": "alive", "service": "Linkify"}

@app.delete("/delete/{short_code}")
async def delete_url(short_code: str):
    """Delete a short URL"""
    db = get_db()
    
    result = await db.urls.delete_one({"short_code": short_code})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="URL not found")
    
    await db.click_events.delete_many({"short_code": short_code})
    
    return {"message": f"URL {short_code} deleted successfully"}

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
                        max-width: 400px;
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
                        width: 100%;
                        margin: 10px 0;
                        border: 1px solid #2a2a2a;
                        border-radius: 5px;
                        background: #1a1a1a;
                        color: white;
                        font-size: 16px;
                        box-sizing: border-box;
                    }}
                    button {{
                        padding: 12px 24px;
                        background: linear-gradient(135deg, #00d2ff 0%, #3a7bd5 100%);
                        color: white;
                        border: none;
                        border-radius: 5px;
                        cursor: pointer;
                        font-weight: 600;
                        width: 100%;
                        font-size: 16px;
                    }}
                    button:hover {{
                        transform: translateY(-2px);
                    }}
                    .back-link {{
                        margin-top: 1rem;
                        display: block;
                        color: #666;
                        font-size: 14px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h2>🔒 Password Protected Link</h2>
                    <p>This link requires a password to access</p>
                    <form method="get">
                        <input type="password" name="password" placeholder="Enter password" autofocus>
                        <button type="submit">Unlock Link</button>
                    </form>
                    <a href="/" class="back-link">← Back to Home</a>
                </div>
            </body>
            </html>
            """)
        
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