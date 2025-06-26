"""Microsoft Graph API client for DPL Receptionist."""
from typing import Optional, List, Dict, Any
from msgraph import GraphServiceClient
from azure.identity import ClientSecretCredential
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_graph_client(tenant_id: str, client_id: str, client_secret: str, scopes: Optional[List[str]] = None) -> Optional[GraphServiceClient]:
    """Initialize Microsoft Graph client with delegated or application permissions."""
    try:
        # Create credential object
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        
        # If no scopes provided, use default application permissions
        if not scopes:
            scopes = ["https://graph.microsoft.com/.default"]
            
        client = GraphServiceClient(credentials=credential, scopes=scopes)
        
        logger.info(f"Successfully created Graph client with scopes: {scopes}")
        return client
        
    except Exception as e:
        logger.error(f"Failed to initialize Graph client: {str(e)}")
        return None

async def search_users(client: GraphServiceClient, search_term: str) -> Optional[List[Dict[str, Any]]]:
    """Search for users in the organization using Microsoft Graph API."""
    try:
        logger.info(f"Searching users with term: {search_term}")
        
        # Build the request with proper parameters
        filter_query = f"startswith(displayName,'{search_term}') or startswith(mail,'{search_term}')"
        select = ["id", "displayName", "mail", "jobTitle", "department"]
        
        # Make the request
        response = await client.users.get()
        
        if not response or not hasattr(response, 'value'):
            logger.warning("No users found or unexpected response format")
            return None
            
        users = response.value
        logger.info(f"Successfully retrieved {len(users)} users")
        
        # Filter results on the client side since $filter isn't working
        filtered_users = [
            user for user in users 
            if search_term.lower() in (getattr(user, 'display_name', '').lower() or '') or 
               search_term.lower() in (getattr(user, 'mail', '').lower() or '')
        ]
        
        return filtered_users
        
    except Exception as e:
        logger.error(f"Failed to search users: {str(e)}")
        return None

async def get_users(client: GraphServiceClient) -> Optional[List[Dict[str, Any]]]:
    """Get all users from Microsoft Graph API."""
    try:
        logger.info("Getting all users from Graph API")
        response = await client.users.get()
        
        if not response or not hasattr(response, 'value'):
            logger.warning("No users found or unexpected response format")
            return None
            
        users = response.value
        logger.info(f"Successfully retrieved {len(users)} users")
        return users
        
    except Exception as e:
        logger.error(f"Failed to get users: {str(e)}")
        return None
            
    except Exception as e:
        print(f"[ERROR] Failed to create Graph client: {str(e)}")
        return None
