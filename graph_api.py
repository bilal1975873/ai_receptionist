"""Microsoft Graph API helper functions for DPL Receptionist."""
from msgraph import GraphServiceClient
from azure.identity import ClientSecretCredential
from typing import Optional, Dict, List, Any
import os
import asyncio

async def get_users(graph_client: GraphServiceClient) -> Optional[List[Dict[str, Any]]]:
    """Get all users from Microsoft Graph API."""
    try:
        print("[DEBUG] Getting users from Graph API")
        response = await graph_client.users.get()
        
        if not response:
            print("[ERROR] No response from Graph API")
            return None
            
        if not hasattr(response, 'value'):
            print("[ERROR] Unexpected response format - no 'value' attribute")
            print(f"[DEBUG] Response type: {type(response)}")
            return None
            
        users = response.value
        print(f"[DEBUG] Successfully retrieved {len(users)} users")
        return users
        
    except Exception as e:
        print(f"[ERROR] Failed to get users: {str(e)}")
        return None

def initialize_graph_client(tenant_id: str, client_id: str, client_secret: str) -> Optional[GraphServiceClient]:
    """Initialize Microsoft Graph client with application permissions."""
    try:
        # Create credential object
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        
        # Create Graph client
        client = GraphServiceClient(credentials=credential)
        
        print("[DEBUG] Successfully created Graph client")
        return client
        
    except Exception as e:
        print(f"[ERROR] Failed to initialize Graph client: {str(e)}")
        return None
