from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from dotenv import load_dotenv
from typing import Optional
from urllib.parse import quote
from auth_utils import clear_tokens, log
from auth_manager import AuthManager
import os
import secrets
import requests
import time
import json

# Load environment variables
load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8000/auth/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
SCOPES = "https://graph.microsoft.com/User.Read openid profile offline_access"
TOKEN_FILE = "tokens.json"

router = APIRouter()
auth_manager = AuthManager()

def redirect_with_error(message: str, error_code: Optional[str] = None):
    """Helper function to create error redirects"""
    params = [f"error=true", f"message={quote(message)}"]
    if error_code:
        params.append(f"error_code={error_code}")
    return RedirectResponse(
        url=f"{FRONTEND_URL}/login?{'&'.join(params)}",
        status_code=302
    )

def is_logged_in(request: Request) -> bool:
    return "access_token" in request.session

@router.get("/login")
async def login(request: Request):
    # log("Login started")
    try:
        # Validate required environment variables
        if not all([CLIENT_ID, TENANT_ID, CLIENT_SECRET, REDIRECT_URI]):
            # log("Missing required environment variables")
            return redirect_with_error("Missing configuration", "CONFIG_ERROR")

        # Clean any existing session data
        request.session.clear()

        # Generate and store state in session
        state = secrets.token_urlsafe(32)
        request.session['auth_state'] = state
        
        # log(f"Session data before update: {dict(request.session)}")
        # No need to call request.session.update() or .save()
        # log(f"Session data after update: {dict(request.session)}")
        
        encoded_redirect_uri = quote(REDIRECT_URI)
        encoded_scopes = quote(SCOPES)
        
        auth_url = (
            f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/authorize"
            f"?client_id={CLIENT_ID}"
            f"&response_type=code"
            f"&redirect_uri={encoded_redirect_uri}"
            f"&response_mode=query"
            f"&scope={encoded_scopes}"
            f"&state={state}"
            f"&prompt=select_account"
        )
        
        # log(f"Generated auth URL: {auth_url}")
        return RedirectResponse(url=auth_url, status_code=302)
        
    except Exception as e:
        # log(f"Login error: {str(e)}")
        return redirect_with_error(str(e), "UNEXPECTED_ERROR")

@router.get("/callback")
async def auth_callback(
    request: Request,
    code: Optional[str] = None,
    error: Optional[str] = None,
    state: Optional[str] = None
):
    if error:
        log(f"Auth error: {error}")
        return redirect_with_error(f"Authentication failed: {error}")
    
    if not code:
        log("No code provided in callback")
        return redirect_with_error("No authorization code received")
    
    # Verify state parameter
    stored_state = request.session.get('auth_state')
    log(f"Verifying state. Got {state}, stored {stored_state}")
    
    if not stored_state:
        log("No stored state found")
        return redirect_with_error("Invalid session state", "STATE_ERROR")
    
    # In development, we'll log state mismatch but continue
    # In production, you should enforce state verification
    if state != stored_state:
        if os.getenv("ENVIRONMENT") == "production":
            return redirect_with_error("State mismatch", "STATE_ERROR")
        log("State mismatch, but proceeding with auth in development")
    
    try:
        # Exchange the authorization code for tokens
        token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
        data = {
            "client_id": CLIENT_ID,
            "scope": SCOPES,
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
            "client_secret": CLIENT_SECRET,
        }
        resp = requests.post(token_url, data=data)
        if resp.status_code != 200:
            log(f"Token exchange failed: {resp.text}")
            return redirect_with_error("Failed to exchange code for token", "TOKEN_ERROR")
        tokens = resp.json()
        # Save tokens to disk for delegated auth
        auth_manager.save_tokens(tokens)
        # Set is_authenticated flag and user info in session
        request.session["is_authenticated"] = True
        # Optionally store user info if available
        if "id_token" in tokens:
            # Decode JWT for user info (optional, not required for auth loop fix)
            import base64, json
            try:
                payload = tokens["id_token"].split(".")[1]
                # Pad base64 if needed
                payload += '=' * (-len(payload) % 4)
                user_info = json.loads(base64.urlsafe_b64decode(payload))
                request.session["user"] = user_info
            except Exception as e:
                log(f"Failed to decode id_token: {e}")
        # log(f"Session after login: {dict(request.session)}")
        # Redirect to frontend dashboard/home after successful login
        return RedirectResponse(url=FRONTEND_URL, status_code=302)
    except Exception as e:
        # log(f"Callback error: {str(e)}")
        return redirect_with_error(str(e), "UNEXPECTED_ERROR")

@router.get("/logout")
async def logout(request: Request):
    try:
        request.session.clear()
        clear_tokens()
        return RedirectResponse(
            url=f"{FRONTEND_URL}/login?logged_out=true",
            status_code=302
        )
    except Exception as e:
        # log(f"Logout error: {str(e)}")
        return redirect_with_error("Logout failed", "LOGOUT_ERROR")

@router.get("/me")
async def get_current_user(request: Request):
    """Get current user info from session"""
    try:
        # Get access token from session
        access_token = request.session.get('access_token')
        if not access_token:
            raise HTTPException(status_code=401, detail="Not authenticated")

        # Get user info from session
        user_info = request.session.get('user')
        if not user_info:
            raise HTTPException(status_code=401, detail="User info not found")

        return JSONResponse(user_info)
    except Exception as e:
        # log(f"Error getting user info: {str(e)}")
        raise HTTPException(status_code=401, detail="Authentication error")

@router.get("/check")
async def check_auth(request: Request):
    """Check if the user is authenticated"""
    try:
        # log(f"/auth/check headers: {dict(request.headers)}")
        # log(f"/auth/check session: {dict(request.session)}")
        if not request.session.get("is_authenticated"):
            # log("User is not authenticated (no is_authenticated flag)")
            return JSONResponse(status_code=401, content={"authenticated": False})
        return {"authenticated": True}
    except Exception as e:
        # log(f"/auth/check error: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})