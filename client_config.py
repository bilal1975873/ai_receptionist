# client_config.py
from azure.identity import ClientSecretCredential
from typing import Optional, List

# Required application permissions for Teams message sending
REQUIRED_PERMISSIONS = [
    'Chat.Create',           # Required to create new chats
    'Chat.ReadWrite',       # Required to send messages
    'User.Read.All'         # Required to look up users
]

class ClientConfig:
    """Handles Microsoft Graph API authentication with application permissions."""
    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self._token = None
    
    def get_token(self, scope: Optional[str] = None) -> str:
        """
        Get an access token for Microsoft Graph API with application permissions.
        The token will have all required permissions for Teams message sending.
        """
        try:
            if not self._token:
                print("[INFO] Getting new access token with application permissions")
                
                # Create credential object for application permissions
                credential = ClientSecretCredential(
                    tenant_id=self.tenant_id,
                    client_id=self.client_id,
                    client_secret=self.client_secret
                )
                
                # Use .default scope for application permissions
                self._token = credential.get_token("https://graph.microsoft.com/.default")
                print("[INFO] Successfully acquired new access token")
                
            return self._token.token
            
        except Exception as e:
            error_msg = str(e)
            print(f"[ERROR] Failed to get access token: {error_msg}")
            
            if "invalid_client" in error_msg.lower():
                print("[ERROR] Invalid client credentials. Please check CLIENT_ID and CLIENT_SECRET")
            elif "unauthorized_client" in error_msg.lower():
                print("[ERROR] Unauthorized client. Please verify app registration and permissions")
            
            raise  # Re-raise the exception after logging
