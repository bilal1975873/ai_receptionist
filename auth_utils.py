import os
import json
import time
import requests
from fastapi import HTTPException
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8000/auth/callback")
# Define scopes as a list to avoid conversion issues
SCOPES = [
    'User.Read',
    'Chat.ReadWrite',
    'Chat.Create',
    'Calendars.ReadWrite',
    'openid',
    'profile',
    'offline_access'
]
TOKEN_FILE = "tokens.json"

def log(msg):
    print(f"[LOG] {msg}")

def save_tokens(tokens):
    with open(TOKEN_FILE, "w") as f:
        json.dump(tokens, f)

def load_tokens():
    if not os.path.exists(TOKEN_FILE):
        return None
    with open(TOKEN_FILE, "r") as f:
        return json.load(f)

def clear_tokens():
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)

def is_token_expired(tokens):
    return time.time() > tokens.get("expiration_time", 0)

def refresh_access_token(tokens):
    log("Token expired — refreshing")
    token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = {
        "client_id": CLIENT_ID,
        "scope": " ".join(SCOPES),  # Join scopes with spaces for token request
        "refresh_token": tokens["refresh_token"],
        "grant_type": "refresh_token",
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
    }
    resp = requests.post(token_url, data=data)
    if resp.status_code == 200:
        new_tokens = resp.json()
        tokens["access_token"] = new_tokens["access_token"]
        tokens["refresh_token"] = new_tokens.get("refresh_token", tokens["refresh_token"])
        tokens["expires_in"] = new_tokens["expires_in"]
        tokens["expiration_time"] = time.time() + new_tokens["expires_in"] - 60
        save_tokens(tokens)
        log("Access token refreshed")
        return tokens
    else:
        log("Token refresh failed — please log in again")
        clear_tokens()
        return None

def get_valid_tokens():
    tokens = load_tokens()
    if not tokens:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in.")
    if is_token_expired(tokens):
        tokens = refresh_access_token(tokens)
        if not tokens:
            raise HTTPException(status_code=401, detail="Token refresh failed. Please log in again.")
    return tokens