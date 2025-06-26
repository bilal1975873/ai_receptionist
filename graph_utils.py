"""Microsoft Graph API helper functions for DPL Receptionist."""

from msgraph import GraphServiceClient
from azure.identity import ClientSecretCredential
from typing import Optional, Dict, List, Any
import asyncio
import os

def create_graph_client(tenant_id: str, client_id: str, client_secret: str) -> Optional[GraphServiceClient]:
    """Initialize Microsoft Graph client with application permissions."""
    try:
        print("[DEBUG] Creating Graph client...")
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        
        client = GraphServiceClient(credentials=credential)
        print("[DEBUG] Graph client created successfully")
        return client
        
    except Exception as e:
        print(f"[ERROR] Failed to create Graph client: {str(e)}")
        return None

async def get_users(client: GraphServiceClient) -> Optional[List[Dict[str, Any]]]:
    """Get all users from Microsoft Graph API."""
    try:
        print("[DEBUG] Getting users from Graph API")
        response = await client.users.get()
        if response and hasattr(response, 'value'):
            print(f"[DEBUG] Got {len(response.value)} users")
            return response.value
        print("[ERROR] Invalid response from Graph API")
        return None
        
    except Exception as e:
        print(f"[ERROR] Failed to get users: {str(e)}")
        return None
