"""Authentication manager for delegated permissions."""
import os
import json
import time
import requests
import threading
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def log(msg):
    print(f"[LOG] {msg}")

class AuthManager:
    def __init__(self):
        self.token_file = "tokens.json"
        self.token_file_abs = os.path.abspath(self.token_file)
        self.client_id = os.getenv("CLIENT_ID")
        self.tenant_id = os.getenv("TENANT_ID")
        self.client_secret = os.getenv("CLIENT_SECRET")        
        self.redirect_uri = os.getenv("REDIRECT_URI", "http://localhost:8000/auth/callback")
        self.scope = "offline_access User.Read Chat.ReadWrite"  # Space-separated list of scopes
        self._token_lock = threading.Lock()
        # Defensive: ensure _token_lock always exists
        log("[DEBUG] AuthManager initialized with token lock.")

    def save_tokens(self, tokens):
        try:
            log(f"Saving tokens to {self.token_file_abs}")
            with open(self.token_file_abs, "w") as f:
                json.dump(tokens, f)
            log("Tokens saved successfully.")
        except Exception as e:
            log(f"Error saving tokens: {e}")

    def load_tokens(self):
        try:
            log(f"Loading tokens from {self.token_file_abs}")
            if not os.path.exists(self.token_file_abs):
                log("Token file does not exist.")
                return None
            with open(self.token_file_abs, "r") as f:
                tokens = json.load(f)
            log("Tokens loaded successfully.")
            return tokens
        except Exception as e:
            log(f"Error loading tokens: {e}")
            return None

    def clear_tokens(self):
        try:
            log(f"Clearing tokens at {self.token_file_abs}")
            if os.path.exists(self.token_file_abs):
                os.remove(self.token_file_abs)
                log("Tokens cleared.")
            else:
                log("No token file to clear.")
        except Exception as e:
            log(f"Error clearing tokens: {e}")

    def is_token_expired(self, tokens):
        return time.time() > tokens.get("expiration_time", 0)

    def refresh_access_token(self, tokens):
        log("Token expired — refreshing")
        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        data = {
            "client_id": self.client_id,
            "scope": self.scope,
            "refresh_token": tokens["refresh_token"],
            "grant_type": "refresh_token",
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
        }
        resp = requests.post(token_url, data=data)
        if resp.status_code == 200:
            new_tokens = resp.json()
            tokens["access_token"] = new_tokens["access_token"]
            tokens["refresh_token"] = new_tokens.get("refresh_token", tokens["refresh_token"])
            tokens["expires_in"] = new_tokens["expires_in"]
            tokens["expiration_time"] = time.time() + new_tokens["expires_in"] - 60
            self.save_tokens(tokens)
            log("Access token refreshed")
            return tokens
        else:
            log("Token refresh failed — please log in again")
            self.clear_tokens()
            return None

    def get_valid_token(self):
        tokens = self.load_tokens()
        if not tokens:
            log("No tokens found - user needs to authenticate")
            return None
            
        if self.is_token_expired(tokens):
            tokens = self.refresh_access_token(tokens)
            if not tokens:
                return None
                
        return tokens["access_token"]

    def get_token_info(self):
        """Get the full token info including refresh token."""
        # Use the token lock for thread safety
        if not hasattr(self, '_token_lock'):
            self._token_lock = threading.Lock()
        with self._token_lock:
            tokens = self.load_tokens()
            if not tokens:
                log("No tokens found in get_token_info")
                return None
            log(f"[DEBUG] Returning token info: {tokens}")
            return tokens
