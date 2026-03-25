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
    """Serve the homepage - only URL shortener"""
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
        if url.get('expires_at'):
            expires_date = url['expires_at'].strftime('%Y-%m-%d')
            expires_info = f"📅 Expires: {expires_date}"
        
        # Show password info if exists
        password_info = ""
        if url.get('is_password_protected'):
            password_info = "🔒 Password Protected"
        
        urls_html += f"""
        <div class="url-row" id="row-{url['short_code']}">
            <div class="short-url-col">
                <a href="/{url['short_code']}" target="_blank" class="short-url-link">
                    {settings.BASE_URL}/{url['short_code']}
                </a>
                <div class="url-actions">
                    <a href="{qr_link}" target="_blank" class="action-btn qr-btn" title="Generate QR Code">📱 QR Code</a>
                    <button onclick="{delete_link}" class="action-btn delete-btn" title="Delete URL">🗑️ Delete</button>
                </div>
            </div>
            <div class="long-url" title="{url['long_url']}">
                {url['long_url'][:60]}{'...' if len(url['long_url']) > 60 else ''}
            </div>
            <div class="url-info">
                <span class="clicks-count">👁️ {url.get('clicks', 0)} clicks</span>
                {f'<span class="expiry-badge">{expires_info}</span>' if expires_info else ''}
                {f'<span class="password-badge">{password_info}</span>' if password_info else ''}
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
                            <a href="/feature/custom-code">✨ Custom Short Code</a>
                            <a href="/feature/qr-code">📱 QR Code</a>
                            <a href="/feature/expiration">⏰ URL Expiration</a>
                            <a href="/feature/password">🔒 Password Protection</a>
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

# ============ FEATURE PAGES (Each with its own form) ============

@app.get("/feature/custom-code", response_class=HTMLResponse)
async def custom_code_page(request: Request):
    """Custom short codes feature page with form"""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Custom Short Code - Linkify</title>
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
                            <a href="/feature/custom-code" class="active">✨ Custom Short Code</a>
                            <a href="/feature/qr-code">📱 QR Code</a>
                            <a href="/feature/expiration">⏰ URL Expiration</a>
                            <a href="/feature/password">🔒 Password Protection</a>
                        </div>
                    </div>
                    <a href="/about" class="nav-link">About</a>
                </div>
            </div>
        </nav>

        <div class="feature-page">
            <div class="feature-header">
                <h1>✨ Custom Short Code</h1>
                <p>Create a memorable, branded link with your own custom code</p>
            </div>

            <div class="feature-content">
                <div class="feature-card-large">
                    <h2>Create Your Custom Short URL</h2>
                    <form id="shortenForm" class="feature-form">
                        <div class="form-group">
                            <label>🔗 Long URL</label>
                            <input type="url" id="longUrl" placeholder="https://example.com/your-long-url" required>
                        </div>
                        <div class="form-group">
                            <label>✨ Custom Short Code</label>
                            <input type="text" id="customCode" placeholder="my-custom-link (letters, numbers, hyphens only)" required>
                            <small>Example: mywebsite, portfolio, link2026</small>
                        </div>
                        <button type="submit" class="btn-primary">Create Custom Short URL →</button>
                    </form>
                    
                    <div id="result" style="display: none; margin-top: 2rem; padding: 1rem; background: #1a1a1a; border-radius: 8px;">
                        <p>✅ <strong>Your short URL is ready!</strong></p>
                        <code id="shortUrl" style="color: #00d2ff; word-break: break-all;"></code>
                        <button onclick="copyUrl()" class="copy-btn" style="margin-left: 1rem;">📋 Copy</button>
                    </div>
                    
                    <div id="error" style="display: none; margin-top: 2rem; padding: 1rem; background: rgba(255,0,0,0.1); border-radius: 8px; color: #ff8888;"></div>
                </div>

                <div class="feature-tip">
                    <strong>💡 Examples of great custom codes:</strong>
                    <div class="example-list">
                        <div class="example-item">🔗 linkify.onrender.com/<strong>myportfolio</strong></div>
                        <div class="example-item">🔗 linkify.onrender.com/<strong>instagram</strong></div>
                        <div class="example-item">🔗 linkify.onrender.com/<strong>sale2026</strong></div>
                    </div>
                </div>
            </div>
        </div>

        <footer class="footer">
            <div class="footer-container">
                <p>&copy; 2026 Linkify - Make your links shorter and smarter</p>
            </div>
        </footer>

        <script>
        document.getElementById('shortenForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const longUrl = document.getElementById('longUrl').value;
            const customCode = document.getElementById('customCode').value;
            
            const resultDiv = document.getElementById('result');
            const errorDiv = document.getElementById('error');
            resultDiv.style.display = 'none';
            errorDiv.style.display = 'none';
            
            try {
                const response = await fetch('/shorten', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({long_url: longUrl, custom_code: customCode})
                });
                const data = await response.json();
                if (response.ok) {
                    document.getElementById('shortUrl').innerHTML = data.short_url;
                    resultDiv.style.display = 'block';
                    document.getElementById('longUrl').value = '';
                    document.getElementById('customCode').value = '';
                } else {
                    errorDiv.innerHTML = '<strong>⚠️ Error:</strong> ' + data.detail;
                    errorDiv.style.display = 'block';
                }
            } catch(err) {
                errorDiv.innerHTML = '<strong>⚠️ Error:</strong> Failed to create URL';
                errorDiv.style.display = 'block';
            }
        });
        
        function copyUrl() {
            const url = document.getElementById('shortUrl').innerHTML;
            navigator.clipboard.writeText(url);
            alert('✅ Copied to clipboard!');
        }
        </script>
    </body>
    </html>
    """)

@app.get("/feature/qr-code", response_class=HTMLResponse)
async def qr_code_page(request: Request):
    """QR Code feature page with form"""
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
                            <a href="/feature/custom-code">✨ Custom Short Code</a>
                            <a href="/feature/qr-code" class="active">📱 QR Code</a>
                            <a href="/feature/expiration">⏰ URL Expiration</a>
                            <a href="/feature/password">🔒 Password Protection</a>
                        </div>
                    </div>
                    <a href="/about" class="nav-link">About</a>
                </div>
            </div>
        </nav>

        <div class="feature-page">
            <div class="feature-header">
                <h1>📱 QR Code Generator</h1>
                <p>Generate QR codes for any URL - perfect for business cards, posters, and more!</p>
            </div>

            <div class="feature-content">
                <div class="feature-card-large">
                    <h2>Generate QR Code</h2>
                    <form id="qrForm" class="feature-form">
                        <div class="form-group">
                            <label>🔗 Enter URL to generate QR code</label>
                            <input type="url" id="urlInput" placeholder="https://example.com/your-link" required>
                        </div>
                        <button type="submit" class="btn-primary">Generate QR Code →</button>
                    </form>
                    
                    <div id="qrResult" style="display: none; margin-top: 2rem; text-align: center;">
                        <div style="background: white; padding: 1rem; border-radius: 12px; display: inline-block;">
                            <img id="qrImage" src="" alt="QR Code" style="width: 200px; height: 200px;">
                        </div>
                        <div style="margin-top: 1rem;">
                            <button onclick="downloadQR()" class="btn-primary">📥 Download QR Code</button>
                        </div>
                    </div>
                    
                    <div id="error" style="display: none; margin-top: 2rem; padding: 1rem; background: rgba(255,0,0,0.1); border-radius: 8px; color: #ff8888;"></div>
                </div>

                <div class="feature-tip">
                    <strong>💡 Perfect for:</strong> Business cards, product packaging, event flyers, social media profiles, restaurant menus
                </div>
            </div>
        </div>

        <footer class="footer">
            <div class="footer-container">
                <p>&copy; 2026 Linkify - Make your links shorter and smarter</p>
            </div>
        </footer>

        <script>
        document.getElementById('qrForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const url = document.getElementById('urlInput').value;
            const errorDiv = document.getElementById('error');
            const qrResult = document.getElementById('qrResult');
            errorDiv.style.display = 'none';
            qrResult.style.display = 'none';
            
            try {
                const response = await fetch('/generate-qr', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url: url})
                });
                const data = await response.json();
                if (response.ok) {
                    document.getElementById('qrImage').src = data.qr_code;
                    qrResult.style.display = 'block';
                } else {
                    errorDiv.innerHTML = '<strong>⚠️ Error:</strong> ' + data.detail;
                    errorDiv.style.display = 'block';
                }
            } catch(err) {
                errorDiv.innerHTML = '<strong>⚠️ Error:</strong> Failed to generate QR code';
                errorDiv.style.display = 'block';
            }
        });
        
        function downloadQR() {
            const img = document.getElementById('qrImage');
            const link = document.createElement('a');
            link.download = 'qrcode.png';
            link.href = img.src;
            link.click();
        }
        </script>
    </body>
    </html>
    """)

@app.get("/feature/expiration", response_class=HTMLResponse)
async def expiration_page(request: Request):
    """URL Expiration feature page with form"""
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
                            <a href="/feature/custom-code">✨ Custom Short Code</a>
                            <a href="/feature/qr-code">📱 QR Code</a>
                            <a href="/feature/expiration" class="active">⏰ URL Expiration</a>
                            <a href="/feature/password">🔒 Password Protection</a>
                        </div>
                    </div>
                    <a href="/about" class="nav-link">About</a>
                </div>
            </div>
        </nav>

        <div class="feature-page">
            <div class="feature-header">
                <h1>⏰ URL Expiration</h1>
                <p>Create links that automatically expire after a set number of days</p>
            </div>

            <div class="feature-content">
                <div class="feature-card-large">
                    <h2>Create Expiring Link</h2>
                    <form id="expirationForm" class="feature-form">
                        <div class="form-group">
                            <label>🔗 Long URL</label>
                            <input type="url" id="longUrl" placeholder="https://example.com/your-link" required>
                        </div>
                        <div class="form-group">
                            <label>⏰ Expires in (days)</label>
                            <input type="number" id="expiresDays" placeholder="7" min="1" max="365" required>
                            <small>Link will stop working after this many days</small>
                        </div>
                        <button type="submit" class="btn-primary">Create Expiring Link →</button>
                    </form>
                    
                    <div id="result" style="display: none; margin-top: 2rem; padding: 1rem; background: #1a1a1a; border-radius: 8px;">
                        <p>✅ <strong>Your expiring short URL is ready!</strong></p>
                        <code id="shortUrl" style="color: #00d2ff; word-break: break-all;"></code>
                        <p style="margin-top: 0.5rem; font-size: 0.9rem; color: #ffa500;">⏰ This link will expire in <span id="expiresIn"></span> days</p>
                        <button onclick="copyUrl()" class="copy-btn" style="margin-left: 1rem;">📋 Copy</button>
                    </div>
                    
                    <div id="error" style="display: none; margin-top: 2rem; padding: 1rem; background: rgba(255,0,0,0.1); border-radius: 8px; color: #ff8888;"></div>
                </div>

                <div class="feature-tip">
                    <strong>💡 Perfect for:</strong> Limited-time promotions, event invitations, temporary access links, seasonal campaigns
                </div>
            </div>
        </div>

        <footer class="footer">
            <div class="footer-container">
                <p>&copy; 2026 Linkify - Make your links shorter and smarter</p>
            </div>
        </footer>

        <script>
        document.getElementById('expirationForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const longUrl = document.getElementById('longUrl').value;
            const expiresDays = document.getElementById('expiresDays').value;
            
            const resultDiv = document.getElementById('result');
            const errorDiv = document.getElementById('error');
            resultDiv.style.display = 'none';
            errorDiv.style.display = 'none';
            
            try {
                const response = await fetch('/shorten', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({long_url: longUrl, expires_days: parseInt(expiresDays)})
                });
                const data = await response.json();
                if (response.ok) {
                    document.getElementById('shortUrl').innerHTML = data.short_url;
                    document.getElementById('expiresIn').innerHTML = expiresDays;
                    resultDiv.style.display = 'block';
                    document.getElementById('longUrl').value = '';
                    document.getElementById('expiresDays').value = '';
                } else {
                    errorDiv.innerHTML = '<strong>⚠️ Error:</strong> ' + data.detail;
                    errorDiv.style.display = 'block';
                }
            } catch(err) {
                errorDiv.innerHTML = '<strong>⚠️ Error:</strong> Failed to create URL';
                errorDiv.style.display = 'block';
            }
        });
        
        function copyUrl() {
            const url = document.getElementById('shortUrl').innerHTML;
            navigator.clipboard.writeText(url);
            alert('✅ Copied to clipboard!');
        }
        </script>
    </body>
    </html>
    """)

@app.get("/feature/password", response_class=HTMLResponse)
async def password_page(request: Request):
    """Password Protection feature page with form"""
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
                            <a href="/feature/custom-code">✨ Custom Short Code</a>
                            <a href="/feature/qr-code">📱 QR Code</a>
                            <a href="/feature/expiration">⏰ URL Expiration</a>
                            <a href="/feature/password" class="active">🔒 Password Protection</a>
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
                    <h2>Create Password-Protected Link</h2>
                    <form id="passwordForm" class="feature-form">
                        <div class="form-group">
                            <label>🔗 Long URL</label>
                            <input type="url" id="longUrl" placeholder="https://example.com/your-link" required>
                        </div>
                        <div class="form-group">
                            <label>🔒 Password</label>
                            <input type="password" id="password" placeholder="Enter a strong password" required>
                            <small>Visitors will need this password to access the link</small>
                        </div>
                        <button type="submit" class="btn-primary">Create Protected Link →</button>
                    </form>
                    
                    <div id="result" style="display: none; margin-top: 2rem; padding: 1rem; background: #1a1a1a; border-radius: 8px;">
                        <p>✅ <strong>Your password-protected short URL is ready!</strong></p>
                        <code id="shortUrl" style="color: #00d2ff; word-break: break-all;"></code>
                        <p style="margin-top: 0.5rem; font-size: 0.9rem; color: #ffa500;">🔒 This link is password protected. Share the password separately!</p>
                        <button onclick="copyUrl()" class="copy-btn" style="margin-left: 1rem;">📋 Copy</button>
                    </div>
                    
                    <div id="error" style="display: none; margin-top: 2rem; padding: 1rem; background: rgba(255,0,0,0.1); border-radius: 8px; color: #ff8888;"></div>
                </div>

                <div class="feature-tip">
                    <strong>💡 Security Tips:</strong>
                    <ul style="margin-top: 0.5rem; color: #888;">
                        <li>Use strong passwords with letters, numbers, and symbols</li>
                        <li>Share the password separately from the link</li>
                        <li>Perfect for private documents, personal photos, confidential information</li>
                    </ul>
                </div>
            </div>
        </div>

        <footer class="footer">
            <div class="footer-container">
                <p>&copy; 2026 Linkify - Make your links shorter and smarter</p>
            </div>
        </footer>

        <script>
        document.getElementById('passwordForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const longUrl = document.getElementById('longUrl').value;
            const password = document.getElementById('password').value;
            
            const resultDiv = document.getElementById('result');
            const errorDiv = document.getElementById('error');
            resultDiv.style.display = 'none';
            errorDiv.style.display = 'none';
            
            try {
                const response = await fetch('/shorten', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({long_url: longUrl, password: password})
                });
                const data = await response.json();
                if (response.ok) {
                    document.getElementById('shortUrl').innerHTML = data.short_url;
                    resultDiv.style.display = 'block';
                    document.getElementById('longUrl').value = '';
                    document.getElementById('password').value = '';
                } else {
                    errorDiv.innerHTML = '<strong>⚠️ Error:</strong> ' + data.detail;
                    errorDiv.style.display = 'block';
                }
            } catch(err) {
                errorDiv.innerHTML = '<strong>⚠️ Error:</strong> Failed to create URL';
                errorDiv.style.display = 'block';
            }
        });
        
        function copyUrl() {
            const url = document.getElementById('shortUrl').innerHTML;
            navigator.clipboard.writeText(url);
            alert('✅ Copied to clipboard!');
        }
        </script>
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
                            <a href="/feature/custom-code">✨ Custom Short Code</a>
                            <a href="/feature/qr-code">📱 QR Code</a>
                            <a href="/feature/expiration">⏰ URL Expiration</a>
                            <a href="/feature/password">🔒 Password Protection</a>
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
                        <li>📱 <strong>QR Code Generation</strong> - Generate QR codes for any URL</li>
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
        existing = await db.urls.find_one({"short_code": short_code})
        if existing:
            raise HTTPException(status_code=400, detail="Custom code already taken")
    else:
        short_code = utils.generate_random_code()
        existing = await db.urls.find_one({"short_code": short_code})
        while existing:
            short_code = utils.generate_random_code()
            existing = await db.urls.find_one({"short_code": short_code})
    
    # Create URL document
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

@app.post("/generate-qr")
async def generate_qr_code_api(data: dict):
    """Generate QR code for any URL"""
    url = data.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    qr_img = generate_qr_code(url)
    return {"qr_code": f"data:image/png;base64,{qr_img}"}

@app.get("/qr/{short_code}")
async def get_qr_code_page(short_code: str):
    """Get QR code page for a short URL"""
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
            body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #0a0a0a; color: white; }}
            .qr-container {{ background: white; padding: 20px; border-radius: 10px; display: inline-block; margin: 20px; }}
            a {{ color: #00d2ff; text-decoration: none; }}
        </style>
    </head>
    <body>
        <h1>📱 QR Code for your link</h1>
        <div class="qr-container">
            <img src="data:image/png;base64,{qr_img}" alt="QR Code">
        </div>
        <p>{short_url}</p>
        <a href="/dashboard">← Back to Dashboard</a>
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
    """Redirect short URL to original URL"""
    db = get_db()
    
    url_data = await db.urls.find_one({"short_code": short_code, "is_active": True})
    
    if not url_data:
        raise HTTPException(status_code=404, detail="URL not found")
    
    if url_data.get("expires_at") and url_data["expires_at"] < datetime.utcnow():
        raise HTTPException(status_code=410, detail="This link has expired")
    
    if url_data.get("password"):
        if not password:
            return HTMLResponse("""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Password Protected - Linkify</title>
                <style>
                    body { font-family: Arial, sans-serif; background: #0a0a0a; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
                    .container { background: #111; padding: 2rem; border-radius: 10px; text-align: center; border: 1px solid #333; }
                    input { padding: 10px; width: 200px; margin: 10px; background: #1a1a1a; border: 1px solid #333; color: white; border-radius: 5px; }
                    button { padding: 10px 20px; background: #00d2ff; color: black; border: none; border-radius: 5px; cursor: pointer; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h2>🔒 Password Protected Link</h2>
                    <form method="get">
                        <input type="password" name="password" placeholder="Enter password" autofocus>
                        <br>
                        <button type="submit">Unlock</button>
                    </form>
                </div>
            </body>
            </html>
            """)
        
        if password != url_data["password"]:
            raise HTTPException(status_code=401, detail="Incorrect password")
    
    await db.urls.update_one(
        {"short_code": short_code},
        {"$inc": {"clicks": 1}}
    )
    
    return RedirectResponse(url=url_data["long_url"])