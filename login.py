import uvicorn
import requests
import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
import dotenv

# Load environment variables (for local testing)
dotenv.load_dotenv()

app = FastAPI()

# ==========================================
# 👇 CONFIGURATION 👇
# ==========================================

# 1. YOUR APP CREDENTIALS
# Ensure you add these in Render -> Dashboard -> Environment
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET") 

# 2. YOUR SERVER URL (MUST BE HTTPS)
# ✅ Correct: No trailing slash at the end
BASE_URL = "https://testinstalogin.onrender.com" 

# ==========================================

# Automatically builds the callback URL
REDIRECT_URI = f"{BASE_URL}/auth/callback"

# HTML TEMPLATES
LOGIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Instagram Business Login</title>
    <style>
        body {{ font-family: -apple-system, system-ui, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: #fafafa; }}
        .card {{ background: white; padding: 2.5rem; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); text-align: center; max-width: 400px; border: 1px solid #dbdbdb; }}
        .btn {{ background: #0095f6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; display: inline-block; transition: background 0.2s; }}
        .btn:hover {{ background: #1877f2; }}
        h2 {{ margin-top: 0; color: #262626; }}
        p {{ color: #8e8e8e; margin-bottom: 24px; }}
        .logo {{ font-size: 40px; margin-bottom: 10px; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="logo">📸</div>
        <h2>Instagram Business Login</h2>
        <p>Authenticate to generate your Access Token.</p>
        <a href="/login" class="btn">Log in with Instagram</a>
        <p style="font-size: 12px; margin-top: 20px;">Callback URL configured:<br><code>{callback_url}</code></p>
    </div>
</body>
</html>
"""

RESULT_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Auth Success</title>
    <style>
        body {{ font-family: monospace; padding: 2rem; background: #f4f4f4; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; border: 1px solid #ddd; }}
        h2 {{ color: #2e7d32; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
        .field {{ margin-bottom: 25px; }}
        label {{ font-weight: bold; display: block; margin-bottom: 8px; color: #333; font-size: 1.1em; }}
        textarea {{ width: 100%; height: 100px; padding: 10px; border: 2px solid #ccc; border-radius: 4px; background: #fafafa; font-family: monospace; font-size: 0.9em; }}
        input {{ width: 100%; padding: 10px; border: 2px solid #ccc; border-radius: 4px; background: #fafafa; font-family: monospace; font-size: 1.1em; }}
        .copy-hint {{ font-size: 0.8rem; color: #666; margin-top: 5px; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>✅ Authorization Successful</h2>
        
        <div class="field">
            <label>Instagram User ID:</label>
            <input type="text" value="{user_id}" readonly onclick="this.select()">
        </div>

        <div class="field">
            <label>Long-Lived Access Token (60 Days):</label>
            <textarea readonly onclick="this.select()">{token}</textarea>
            <div class="copy-hint">Keep this safe!</div>
        </div>
        
        <div class="field">
            <label>Permissions:</label>
            <input type="text" value="{permissions}" readonly disabled>
        </div>
    </div>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def root():
    return LOGIN_PAGE.format(callback_url=REDIRECT_URI)

@app.get("/login")
async def login():
    # Scopes for "Instagram Login for Business"
    scope = "instagram_business_basic,instagram_business_manage_messages,instagram_business_manage_comments,instagram_business_content_publish,instagram_business_manage_insights"
    
    auth_url = (
        f"https://www.instagram.com/oauth/authorize?"
        f"client_id={APP_ID}&"
        f"redirect_uri={REDIRECT_URI}&" # <--- IMPORTANT: Added back
        f"scope={scope}&"
        f"response_type=code"
    )
    return RedirectResponse(auth_url)

@app.get("/auth/callback", response_class=HTMLResponse)
async def auth_callback(code: str = None, error: str = None, error_description: str = None):
    if error:
        return f"<h1>Error: {error}</h1><p>{error_description}</p>"
    if not code:
        return "<h1>Error: No code received</h1>"

    # 1. Exchange Code for Short-Lived Token (POST to api.instagram.com)
    token_url = "https://api.instagram.com/oauth/access_token"
    
    payload = {
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI, # <--- IMPORTANT: Added back
        "code": code
    }
    
    # Note: This endpoint requires data (form-data), not params
    resp = requests.post(token_url, data=payload)
    data = resp.json()
    
    if "error_type" in data or "access_token" not in data:
        return f"<h1>Token Exchange Failed</h1><p>{data}</p>"
    
    short_token = data.get("access_token")
    user_id = data.get("user_id") 
    permissions = data.get("permissions")

    # 2. Exchange Short-Lived for Long-Lived Token (GET to graph.instagram.com)
    long_token_url = "https://graph.instagram.com/access_token"
    long_params = {
        "grant_type": "ig_exchange_token",
        "client_secret": APP_SECRET,
        "access_token": short_token
    }
    
    long_resp = requests.get(long_token_url, params=long_params)
    long_data = long_resp.json()
    
    if "error" in long_data:
        return f"<h1>Long-Lived Exchange Failed</h1><p>{long_data}</p>"
    
    long_lived_token = long_data.get("access_token")

    return RESULT_PAGE.format(
        user_id=user_id, 
        token=long_lived_token,
        permissions=permissions
    )

if __name__ == "__main__":
    # This allows it to run on Render (which uses PORT env var) or Localhost
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
