from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import RedirectResponse
import os
import urllib.parse
import requests
from fastapi.middleware.cors import CORSMiddleware
from aco.common.logger import logger
from aco.server.edit_manager import EDIT

app = FastAPI()

# CORS configuration: allow frontend origin(s) to call these endpoints
# Use FRONTEND_ORIGIN or ALLOWED_ORIGINS env var (comma separated)
frontend_origin = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")
allowed_env = os.environ.get("ALLOWED_ORIGINS", frontend_origin)
allowed_origins = [o.strip() for o in allowed_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
CALLBACK_URL = os.environ.get("GOOGLE_CALLBACK_URL", "https://agops-project.com/api/auth/google/callback")

AUTH_SCOPE = "openid email profile"


@app.get("/auth/google/url")
def google_url(redirect_uri: str = None):
    """Get Google OAuth URL. Optionally accepts custom redirect_uri for VSCode extension."""
    # Use provided redirect_uri (for VSCode) or default CALLBACK_URL (for web)
    actual_redirect_uri = redirect_uri if redirect_uri else CALLBACK_URL
    
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": actual_redirect_uri,
        "response_type": "code",
        "scope": AUTH_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return {"url": url}


@app.post("/auth/google/callback")
def google_callback(payload: dict, response: Response):
    """Exchange authorization code for user info. Accepts optional redirect_uri."""
    code = payload.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing code")
    
    # Allow custom redirect_uri for VSCode flow
    redirect_uri = payload.get("redirect_uri", CALLBACK_URL)
    
    user, access_token = _process_code_and_upsert(code, response, redirect_uri)
    return {"user": dict(user), "accessToken": access_token}


def _process_code_and_upsert(code: str, response: Response, redirect_uri: str = None):
    """Exchange code for token and upsert user. Accepts custom redirect_uri."""
    actual_redirect_uri = redirect_uri if redirect_uri else CALLBACK_URL
    
    # Exchange code for token
    token_resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": actual_redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    if token_resp.status_code != 200:
        logger.error(f"Token exchange failed: {token_resp.text}")
        raise HTTPException(status_code=400, detail="Token exchange failed")

    tokens = token_resp.json()
    access_token = tokens.get("access_token")

    userinfo = requests.get(
        "https://openidconnect.googleapis.com/v1/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if userinfo.status_code != 200:
        logger.error(f"Failed to fetch userinfo: {userinfo.text}")
        raise HTTPException(status_code=400, detail="Failed to fetch userinfo")

    profile = userinfo.json()
    google_id = profile.get("sub") or profile.get("id")
    email = profile.get("email")
    name = profile.get("name")
    picture = profile.get("picture")

    # Upsert user into both SQLite and PostgreSQL databases
    try:
        user = EDIT.upsert_user(google_id, email, name, picture)
    except Exception as e:
        logger.error(f"DB error during user upsert: {e}")

    # Set a simple cookie with the user id for session retrieval
    try:
        uid = user['id'] if 'id' in user else user[0]
        secure_flag = os.environ.get("USE_SECURE_COOKIES", "false").lower() == "true"
        # For localhost development, set domain to allow cookie sharing across ports
        domain = None
        if "localhost" in str(request.url):
            domain = "localhost"  # This makes cookie available to all localhost ports
        elif "agops-project.com" in str(request.url):
            # For production, set cookie for the main domain (works for all subdomains)
            domain = ".agops-project.com"
        
        response.set_cookie(
            "user_id",
            str(uid),
            httponly=True,
            samesite="lax",  # Use 'lax' for same-site requests (more secure)
            secure=secure_flag,
            path="/",  # Make cookie available on all paths
            domain=domain,  # Set domain for proper scope
        )
    except Exception:
        # If conversion fails, ignore cookie set
        pass

    return user, access_token


@app.get("/auth/session")
def auth_session(request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return {"user": None}
    row = EDIT.get_user_by_id(user_id)
    if not row:
        return {"user": None}
    return {"user": dict(row)}


@app.post("/auth/logout")
def auth_logout(response: Response):
    response.delete_cookie("user_id")
    return {"ok": True}


@app.get("/auth/google/callback")
def google_callback_get(request: Request):
    # Handle browser redirect from Google (query param ?code=...)
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing code")

    # Process the code, set cookie, then redirect back to frontend
    frontend = os.environ.get("FRONTEND_ORIGIN", "https://agops-project.com")
    response = RedirectResponse(url=frontend)
    _process_code_and_upsert(code, response)
    return response
