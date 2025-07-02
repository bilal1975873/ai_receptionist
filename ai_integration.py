import os
import time
import json
import boto3
import msal
import logging
import threading
import requests
import asyncio
import httpx
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from msgraph import GraphServiceClient
from azure.core.credentials import AccessToken
from fuzzywuzzy import fuzz
from prompts import SYSTEM_PERSONALITY, FLOW_CONSTRAINTS, get_dynamic_prompt, get_confirmation_message, get_error_message, STATIC_PROMPTS, generate_dynamic_ai_prompt
from flows import (
    validate_name, 
    validate_cnic, 
    validate_phone, 
    DYNAMIC_ERROR_MESSAGES,
    validate_email,
    validate_with_context,
    ResponseContext
)
from botocore.exceptions import ClientError
logger = logging.getLogger(__name__)

from graph_client import create_graph_client, search_users, get_users
from msgraph.generated.models.chat_message import ChatMessage
from msgraph.generated.models.item_body import ItemBody
from msgraph.generated.models.body_type import BodyType
from msgraph.generated.models.email_address import EmailAddress
from msgraph.generated.models.attendee import Attendee
from msgraph.generated.models.date_time_time_zone import DateTimeTimeZone
from msgraph.generated.models.location import Location
from msgraph.generated.models.event import Event

# Configure logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(_name_)

# Load environment variables
load_dotenv()

# Microsoft Graph credentials with validation
TENANT_ID = os.getenv("TENANT_ID")
if not TENANT_ID:
    raise ValueError("TENANT_ID environment variable is not set")

CLIENT_ID = os.getenv("CLIENT_ID")
if not CLIENT_ID:
    raise ValueError("CLIENT_ID environment variable is not set")

CLIENT_SECRET = os.getenv("CLIENT_SECRET")
if not CLIENT_SECRET:
    raise ValueError("CLIENT_SECRET environment variable is not set")

class AuthManager:
    def __init__(self):
        self.tenant_id = TENANT_ID
        self.client_id = CLIENT_ID
        self.client_secret = CLIENT_SECRET
        self.authority = f"https://login.microsoftonline.com/{TENANT_ID}"
        self.scopes = "offline_access User.Read Chat.ReadWrite"  # Simplified scopes as per working example
        self.token_file = "tokens.json"
        self.app = None
        self._initialize_app()
        
    def save_tokens(self, tokens):
        """Save tokens to a file"""
        with open(self.token_file, "w") as f:
            json.dump(tokens, f)
            
    def load_tokens(self):
        """Load tokens from file"""
        if not os.path.exists(self.token_file):
            return None
        with open(self.token_file, "r") as f:
            return json.load(f)
            
    def clear_tokens(self):
        """Clear saved tokens"""
        if os.path.exists(self.token_file):
            os.remove(self.token_file)
            
    def is_token_expired(self, tokens):
        """Check if token is expired"""
        return time.time() > tokens.get("expiration_time", 0)

    def _initialize_app(self):
        """Initialize the MSAL confidential client application."""
        try:
            self.app = msal.ConfidentialClientApplication(
                client_id=self.client_id,
                client_credential=self.client_secret,
                authority=self.authority
            )
            print("MSAL app initialized")
        except Exception as e:
            print(f"Error initializing MSAL app: {str(e)}")

    def refresh_access_token(self, tokens):
        """Refresh an expired access token"""
        print("Token expired — refreshing")
        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        data = {
            "client_id": self.client_id,
            "scope": self.scopes,
            "refresh_token": tokens["refresh_token"],
            "grant_type": "refresh_token",
            "client_secret": self.client_secret,
            "redirect_uri": "http://localhost:8000/auth/callback",
        }
        resp = requests.post(token_url, data=data)
        if resp.status_code == 200:
            new_tokens = resp.json()
            tokens["access_token"] = new_tokens["access_token"]
            tokens["refresh_token"] = new_tokens.get("refresh_token", tokens["refresh_token"])
            tokens["expires_in"] = new_tokens["expires_in"]
            tokens["expiration_time"] = time.time() + new_tokens["expires_in"] - 60
            self.save_tokens(tokens)
            print("Access token refreshed")
            return tokens
        else:
            print("Token refresh failed — please log in again")
            self.clear_tokens()
            return None
            
    def get_valid_token(self):
        """Get a valid access token, refreshing if necessary"""
        tokens = self.load_tokens()
        if not tokens:
            print("No tokens found - user needs to authenticate")
            return None
            
        if self.is_token_expired(tokens):
            tokens = self.refresh_access_token(tokens)
            if not tokens:
                return None
                
        return tokens["access_token"]

    def get_token_info(self):
        """Get the full token info including refresh token."""
        with self._token_lock:
            return self._token_cache.copy() if self._token_cache else None

class ResponseContext:
    def __init__(self):
        self.state = {}
        
    def set(self, key: str, value: Any):
        """Set a value in the response context"""
        self.state[key] = value
        
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the response context"""
        return self.state.get(key, default)
        
    def remove(self, key: str):
        """Remove a value from the response context"""
        if key in self.state:
            del self.state[key]

class AIReceptionist:
    def __init__(self, auth_manager=None):
        self._system_account_email = "SaadSaad@DPL660.onmicrosoft.com"  # Admin account for notifications
        self._chat_id_cache = {}  # In-memory cache for chat IDs
        self._chat_id_cache_lock = threading.Lock()
        self._token_cache = {
            'access_token': None,
            'refresh_token': None,
            'expires_at': 0
        }  # Cache for delegated tokens
        self._token_lock = threading.Lock()
        self.bedrock_client = self._initialize_bedrock_client()
        self.graph_client = None  # Will be set per-session with delegated token
        self.auth_manager = auth_manager  # Pass AuthManager instance for delegated tokens
        self.msal_app = None  # Will be initialized when needed
        self.initialized = False
        self.response_context = ResponseContext()
        self.conversation_history = []

    def _cache_token(self, token: str, expiry: datetime = None):
        """Cache a token with optional expiry time"""
        if not expiry:
            expiry = datetime.utcnow() + timedelta(hours=1)
        with self._token_cache_lock:
            self._token_cache = {
                'token': token,
                'expiry': expiry
            }

    def _get_cached_token(self) -> Optional[str]:
        """Get cached token if it exists and is not expired"""
        with self._token_lock:
            if not self._token_cache:
                return None
            
            if time.time() >= self._token_cache.get('expires_at', 0):
                # Token expired, try to refresh it
                if self._token_cache.get('refresh_token'):
                    new_token = self._refresh_delegated_token(self._token_cache['refresh_token'])
                    if new_token:
                        self._cache_delegated_token(new_token)
                        return new_token['access_token']
                return None
                
            return self._token_cache.get('access_token')

    def _initialize_bedrock_client(self):
        try:
            from botocore.config import Config
            aws_region = os.getenv("AWS_REGION", "us-east-1")
            aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
            aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
            if not all([aws_access_key, aws_secret_key]):
                print("Error: Missing required AWS credentials in environment variables")
                return None
            boto_config = Config(read_timeout=3600)
            client = boto3.client(
                "bedrock-runtime",
                region_name=aws_region,
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                config=boto_config
            )
            print(f"Successfully initialized AWS Bedrock client in region {aws_region}")
            return client
        except Exception as e:
            print(f"Error initializing Bedrock client: {e}")
            return None

    def _initialize_graph_client_with_token(self, access_token):
        # Define a local TokenCredential class to avoid ImportError
        import time
        from azure.core.credentials import AccessToken
        class LocalTokenCredential:
            def _init_(self, token):
                self.token = token
            def get_token(self, *scopes, **kwargs):
                return AccessToken(self.token, int(time.time()) + 3600)
        credential = LocalTokenCredential(access_token)
        return GraphServiceClient(credentials=credential)

    def get_dynamic_step_prompt(self, step: str, context: Dict[str, Any]) -> str:
        """Get a context-aware dynamic prompt for the current step"""
        from ai_setup import STEP_GUIDANCE
        
        prompts = STEP_GUIDANCE.get(step, [])
        if not prompts:
            return f"Please provide your {step}"
            
        # Select prompt based on context
        interaction_count = context.get('interaction_count', 0)
        is_error = context.get('is_error', False)
        
        if is_error:
            # Use more helpful prompt after errors
            return prompts[-1]  # Last prompt is usually most detailed
        
        # Rotate through prompts based on interaction count
        index = interaction_count % len(prompts)
        return prompts[index]

    async def search_employee(self, name: str) -> Optional[Dict[str, Any]]:
        """Search for an employee by name using Microsoft Graph API."""
        try:
            #print(f"[DEBUG] Starting employee search for name: {name}")
            # Initialize Graph client with system credentials if not initialized
            if self.graph_client is None:
                if not self.auth_manager:
                    raise Exception("AuthManager not initialized. Please ensure auth_manager is provided during initialization.")
                access_token = self.auth_manager.get_valid_token()
                self.graph_client = self._initialize_graph_client_with_token(access_token)
        
            # Attempt to get user details with retries
            retries = 3
            delay = 2  # Initial delay in seconds
            last_error = None

            while retries > 0:
                try:
                    # print("[DEBUG] Querying users from Microsoft Graph API...")
                    # Use $select to get only needed fields and improve performance
                    select_params = ["displayName", "mail", "department", "jobTitle", "id"]
                    result = await self.graph_client.users.get()

                    if not result or not result.value:
                        #print(f"[ERROR] No users found in the organization")
                        return None
                    
                    # print(f"[DEBUG] Successfully retrieved {len(result.value)} users")
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    # print(f"[ERROR] Attempt {4-retries}/3: Error querying users: {str(e)}")
                    last_error = e
                    retries -= 1
                    if retries > 0:
                        # print(f"[DEBUG] Retrying in {delay} seconds...")
                        await asyncio.sleep(delay)
                        delay *= 2  # Exponential backoff
                    else:
                        # print("[ERROR] Failed to query users after 3 attempts")
                        return None

            if last_error and retries == 0:
                return None

            # Search for matches
            search_name = name.lower().strip()
            matches = []
            
            # print(f"[DEBUG] Searching for matches with name: {search_name}")
            
            # First try exact match
            exact_matches = []
            for user in result.value:
                if not user.display_name or not user.mail:
                    continue
                    
                display_name = user.display_name.lower()
                if search_name == display_name:
                    exact_matches.append({
                        "displayName": user.display_name,
                        "email": user.mail,
                        "department": user.department or "Unknown Department",
                        "jobTitle": user.job_title or "Unknown Title",
                        "id": user.id,
                        "score": 100
                    })
            
            if exact_matches:
                # print(f"[DEBUG] Found exact match: {exact_matches[0]['displayName']}")
                return exact_matches[0]  # Return first exact match
                
            # If no exact match, try fuzzy matching
            # print("[DEBUG] No exact match found, trying fuzzy matching...")
            for user in result.value:
                if not user.display_name or not user.mail:
                    continue
                    
                display_name = user.display_name.lower()
                name_parts = display_name.split()
                
                # Different scoring methods
                scores = [
                    fuzz.ratio(search_name, display_name),  # Exact match score
                    fuzz.partial_ratio(search_name, display_name),  # Partial match score
                    fuzz.token_sort_ratio(search_name, display_name),  # Word order independent score
                    max((fuzz.ratio(search_name, part) for part in name_parts), default=0)  # Best single word match
                ]
                
                # Take highest score from any method
                best_score = max(scores)
                
                if best_score >= 60:  # Threshold for considering it a match
                    # print(f"[DEBUG] Found fuzzy match: {user.display_name} (score: {best_score})")
                    matches.append({
                        "displayName": user.display_name,
                        "email": user.mail,
                        "department": user.department or 'Unknown Department',
                        "jobTitle": user.job_title or 'Unknown Title',
                        "id": user.id,
                        "score": best_score
                    })

            # Sort matches by score
            matches.sort(key=lambda x: x["score"], reverse=True)
            
            # Remove scores before returning
            for match in matches:
                match.pop("score", None)

            if not matches:
                # print(f"[DEBUG] No matches found for name: {name}")
                return None
            elif len(matches) == 1:
                # print(f"[DEBUG] Found single match: {matches[0]['displayName']} ({matches[0]['email']})")
                return matches[0]
            else:
                # print(f"[DEBUG] Found {len(matches)} matches")
                return matches

        except Exception as e:
            # print(f"[ERROR] Error in search_employee: {str(e)}")
            # import traceback
            # traceback.print_exc()
            return None

    async def initialize(self):
        if self.initialized:
            return
            
        try:
            # Validate required environment variables
            if not all([TENANT_ID, CLIENT_ID, CLIENT_SECRET]):
                missing = [var for var, val in {"TENANT_ID": TENANT_ID, "CLIENT_ID": CLIENT_ID, "CLIENT_SECRET": CLIENT_SECRET}.items() if not val]
                raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

            # Initialize AWS Bedrock client
            self.bedrock_client = boto3.client(
                service_name='bedrock-runtime',
                region_name='us-east-1'
            )
            logger.info("Successfully initialized AWS Bedrock client in region us-east-1")

            # Initialize MSAL app
            self.msal_app = msal.ConfidentialClientApplication(
                CLIENT_ID,
                authority=f"https://login.microsoftonline.com/{TENANT_ID}",
                client_credential=CLIENT_SECRET,
            )
            logger.info("MSAL app initialized")

            # Initialize Graph client with validated credentials
            try:
                self.graph_client = create_graph_client(
                    tenant_id=TENANT_ID,
                    client_id=CLIENT_ID,
                    client_secret=CLIENT_SECRET
                )
                if not self.graph_client:
                    raise Exception("Graph client initialization returned None")
                logger.info("Successfully initialized Graph client")
            except Exception as e:
                logger.error(f"Failed to initialize Graph client: {str(e)}")
                raise Exception(f"Graph client initialization failed: {str(e)}")

            self.initialized = True
        except Exception as e:
            logger.error(f"Error initializing AIReceptionist: {str(e)}")
            raise
        
    def _format_claude_request(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Format request for Claude model."""
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
           
        return {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens_to_sample": 900,  # Use class constant
            "temperature": 0.999,
            "messages": messages,
            "top_p": 0.9
            
        }
    def process_visitor_input(self, user_input: str, context: Dict[str, Any]) -> str:
        formatted_context = {
            "visitor_type": context.get("visitor_type", ""),
            "visitor_name": context.get("visitor_name", ""),
            "visitor_cnic": context.get("visitor_cnic", ""),
            "visitor_phone": context.get("visitor_phone", ""),
            "host_requested": context.get("host_requested", ""),
            "host_confirmed": context.get("host_confirmed", ""),
            "purpose": context.get("purpose", ""),
            "current_step": context.get("current_step", "unknown"),
            "supplier": context.get("supplier", ""),
            "group_size": context.get("total_members", 1),
            "members_collected": len(context.get("group_members", [])),
            "next_number": len(context.get("group_members", [])) + 2,
            "flow_type": context.get("visitor_type", ""),
            "validation_error": context.get("validation_error", ""),
            "is_repeated_error": context.get("is_repeated_error", False),  # Track repeated errors
            "previous_input": context.get("previous_input", ""),  # Track previous input
            "interaction_count": context.get("interaction_count", 0),  # Track interaction count
            "previous_step": context.get("previous_step", "")  # Track previous step
        }

        current_step = formatted_context["current_step"]
        flow_type = formatted_context.get("flow_type", formatted_context.get("visitor_type", "guest"))
        # Guest flow completion: static message
        if flow_type == "guest" and current_step == "complete":
            return "Registration successful. Rebel presence incoming — host’s been warned."
        
        # For guest flow, always use Bedrock AI-generated prompt for questions (not generate_dynamic_ai_prompt)
        if flow_type == "guest":
            step_prompt = None  # Do not use generate_dynamic_ai_prompt here
        else:
            step_prompt = get_dynamic_prompt(current_step, flow_type)
        
        # Enhanced prompt construction for more natural conversation
        prompt = f"{SYSTEM_PERSONALITY}\n\n{FLOW_CONSTRAINTS}\n\n"
        
        # Add step-specific guidance
        if step_prompt:
            prompt += f"Current step requirements: {step_prompt}\n\n"
        
        # Add conversation context
        prompt += "Current conversation state:\n"
        relevant_context = {
            k: v for k, v in formatted_context.items() 
            if v and k not in ['validation_error', 'previous_step']
        }
        for key, value in relevant_context.items():
            prompt += f"- {key}: {value}\n"
            
        # Add validation context if there was an error
        if formatted_context.get('validation_error'):
            prompt += f"\nValidation error: {formatted_context['validation_error']}\n"
            
        # Add flow state context
        if formatted_context.get('flow_type'):
            flow_type = formatted_context['flow_type']
            if flow_type == 'guest':
                prompt += "\nCurrent flow: Guest REBEL registration\n"
                # Make responses more dynamic for guest flow
                if formatted_context.get('visitor_name'):
                    prompt += f"\nInteracting with: {formatted_context['visitor_name']}\n"
                if formatted_context.get('validation_error'):
                    error_type = formatted_context['validation_error']
                    is_repeated = formatted_context.get('is_repeated_error', False)
                    if is_repeated:
                        prompt += "\nUser is having repeated validation issues. Be extra helpful but maintain the rebel spirit.\n"
                # Add contextual awareness
                interaction_count = formatted_context.get('interaction_count', 0)
                if interaction_count > 3:
                    prompt += "\nUser has been interacting for a while. Keep them engaged with encouraging responses.\n"
            elif flow_type == 'vendor':
                # For vendor flow, keep using step prompts directly without AI generation
                prompt_text = get_dynamic_prompt(current_step, flow_type)
                if prompt_text:
                    if current_step.startswith('vendor_member_'):
                        member_num = formatted_context.get("member_number", "")
                        prompt_text = prompt_text.replace("{number}", str(member_num))
                    return prompt_text
                return self._get_fallback_response(current_step, formatted_context)
            elif flow_type == 'prescheduled':
                prompt += "\nCurrent flow: Pre-scheduled meeting - Verifying appointment\n"
                
        prompt += f"\nVisitor: {user_input}\n\nAssistant:"

        try:
            if not self.bedrock_client:
                print("Bedrock client not initialized")
                return self._get_fallback_response(current_step, formatted_context)

            rebel_instruction = '''
You are DPL's AI receptionist. Your ONLY job is to output a single, direct, creative, and witty question for the user, in a rebellious, anti-corporate style. 

STRICT RULES:
- Output ONLY the next question for the user. 
- NEVER output code, meta-instructions, explanations, or anything except the question.
- NEVER use labels, preambles, or instructions like "Please enter", "Type your answer", "Your response:", "Here is your question:", etc.
- NEVER output anything except the question itself.
- Each question must be unique, context-aware, and match the current step.

EXAMPLES (DO output like this):
- "Ready to disrupt the ordinary? Drop your alias, rebel!"
- "Who's your partner in innovation at DPL headquarters?"
- "What’s your moniker for today’s rebellion?"

EXAMPLES (DO NOT output like this):
- "Please enter your name:"
- "Your response:"
- "Here is your question:"
- "def ask_name():"
- "As an AI model, I will now ask you for your name."
- "The next step is to provide your name."

If you break these rules, you will be penalized. Output ONLY the question, nothing else.
'''
            step_rule = ""
            if current_step == "host":
                step_rule = (
                    "RULE: Ask the guest, in a rebellious and fun style, for the name of the person they are here to see. Do not output anything else."
                )
            # formatted_prompt = f"""<|im_start|>system\n{rebel_instruction}\n{step_rule}\nCurrent context:\nStep: {current_step}\n{formatted_context}\n\nUser message: {user_input}\n\n{FLOW_CONSTRAINTS}"""
            formatted_prompt = f"""
Human: You are DPL's AI receptionist. Your ONLY job is to output a single, direct, creative, and witty question for the user, in a rebellious, anti-corporate style.

{step_rule}
Current context:
Step: {current_step}
{formatted_context}

User message: {user_input}

{FLOW_CONSTRAINTS}

Assistant:
"""

            
            model_id = os.getenv("AWS_BEDROCK_MODEL_ID", "anthropic.claude-instant-v1")
            # Use Claude Messages API format for Claude 3.5 and above
            if model_id.startswith("us.anthropic.claude-3-5") or model_id.startswith("anthropic.claude-3-5"):
                request_payload = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "messages": [
                        {"role": "user", "content": f"{rebel_instruction}\n{step_rule}\nStep: {current_step}\n{formatted_context}\n\nUser message: {user_input}"}
                    ],
                    "max_tokens": 512,
                    "temperature": 0.9,
                    "top_p": 0.9
                }
            elif model_id.startswith("anthropic.claude"):
                request_payload = self._format_claude_request(formatted_prompt)
            else:
                request_payload = {
                    "prompt": formatted_prompt,
                    "max_tokens_to_sample": 512,
                    "temperature": 0.9,
                    "top_p": 0.9,
                }
            request_body = json.dumps(request_payload, ensure_ascii=False).encode('utf-8')
            
            try:
                # Get model ID from environment variables
                model_id = os.getenv("AWS_BEDROCK_MODEL_ID", "anthropic.claude-instant-v1")
                print(f"[DEBUG] Invoking Bedrock model {model_id}")
                # Invoke Bedrock model with retry logic
                try:
                    response = call_bedrock_with_retries(
                        self.bedrock_client,
                        model_id,
                        request_body,
                        max_retries=5
                    )
                except Exception as e:
                    print(f"[ERROR] Error invoking Bedrock model: {str(e)}")
                    return "Sorry, the system is busy. Please wait a few seconds and try again."

                # Parse response
                try:
                    response_body = json.loads(response.get('body').read().decode('utf-8'))
                except Exception as e:
                    print(f"[ERROR] Failed to parse Bedrock response: {str(e)}")
                    return "Sorry, I encountered a technical issue. Please try again in a moment."

                print(f"[DEBUG] Raw Bedrock response: {json.dumps(response_body, indent=2)}")
                # Claude 3.5/3.0/2.1/2.0/Instant: extract from 'content' if present
                if (model_id.startswith("us.anthropic.claude-3-5") or model_id.startswith("anthropic.claude-3-5")) and "content" in response_body:
                    content_blocks = response_body["content"]
                    generation = " ".join(
                        block["text"] for block in content_blocks if block.get("type") == "text" and block.get("text")
                    ).strip()
                elif model_id.startswith("anthropic.claude") and "content" in response_body:
                    # fallback for older Claude models
                    content_blocks = response_body["content"]
                    generation = " ".join(
                        block["text"] for block in content_blocks if block.get("type") == "text" and block.get("text")
                    ).strip()
                elif "completion" in response_body:
                    generation = response_body["completion"]
                elif "generation" in response_body:
                    generation = response_body["generation"]
                else:
                    print("[ERROR] Unexpected response format from Bedrock")
                    return self._get_fallback_response(current_step, formatted_context)
                generation = generation.strip() if generation else None
                if not generation:
                    print("[ERROR] Empty generation from Bedrock")
                    return self._get_fallback_response(current_step, formatted_context)
                print(f"[DEBUG] Final AI response to frontend: {generation}")
                # For vendor flow, always use step prompts directly
                if current_step.startswith('vendor_'):
                    prompt_text = get_dynamic_prompt(current_step, flow_type)
                    if not prompt_text:
                        print(f"[ERROR] No step prompt found for {current_step}")
                        return self._get_fallback_response(current_step, formatted_context)
                        
                    # Handle member number replacement
                    if current_step.startswith('vendor_member_'):
                        member_num = formatted_context.get("member_number", "")
                        return prompt_text.replace("{number}", str(member_num))
                    return prompt_text
                        
                # Use the step prompts for other flows
                prompt_text = get_dynamic_prompt(current_step, flow_type)
                if prompt_text:
                    prompt_text = get_dynamic_prompt(current_step, flow_type)
                    
                    # Don't personalize scheduled steps
                    if current_step.startswith('scheduled_'):
                        generation = prompt_text
                    # Personalize guest flow responses with name if available
                    else:
                        if formatted_context.get("visitor_name"):
                            visitor_name = formatted_context["visitor_name"]
                            generation = f"{visitor_name}, {prompt_text}"
                        else:
                            generation = prompt_text
                    
                ai_response = generation

                # After 'NEXT QUESTION:', scan forward for the first non-empty, non-meta line as the question
                import re
                lines = [l.strip() for l in ai_response.splitlines()]
                question_line = None
                step_keyword = str(current_step).lower() if current_step else ''
                # 1. If a line starts with 'NEXT QUESTION:' and has text after colon, extract it
                for line in lines:
                    m = re.match(r"^next question[:\- ]+(.*)$", line, re.IGNORECASE)
                    if m:
                        possible_q = m.group(1).strip()
                        if possible_q and possible_q != '```':
                            question_line = possible_q
                            break
                # 2. If a line is exactly 'NEXT QUESTION:', scan forward for first non-empty, non-meta line
                if not question_line:
                    for idx, line in enumerate(lines):
                        if re.match(r"^next question[:\- ]*$", line.strip(), re.IGNORECASE):
                            for next_line in lines[idx+1:]:
                                next_line_stripped = next_line.strip()
                                if next_line_stripped and next_line_stripped != '```' and not next_line_stripped.startswith('```') and not next_line_stripped.startswith('|im_start|') and not re.match(r"^next question[:\- ]*", next_line_stripped, re.IGNORECASE):
                                    question_line = next_line_stripped
                                    break
                            if question_line:
                                break
                # 3. Prefer real, non-meta, non-code-block lines with step keyword and question mark
                if not question_line and step_keyword:
                    for line in lines:
                        if line and line != '```' and step_keyword in line.lower() and '?' in line and not line.startswith('```') and not line.startswith('|im_start|'):
                            question_line = line.strip()
                            break
                # 4. Try to extract after 'Output:'
                if not question_line:
                    for line in lines:
                        m = re.match(r"^output[:\- ]*(.*)$", line, re.IGNORECASE)
                        if m:
                            possible_q = m.group(1).strip()
                            if possible_q and possible_q != '```':
                                question_line = possible_q
                                break
                # 5. Try to find a line with key words and a question mark
                if not question_line:
                    for line in lines:
                        if line and line != '```' and (('cnic' in line.lower() or 'host' in line.lower() or 'name' in line.lower()) and '?' in line) and not line.startswith('```') and not line.startswith('|im_start|'):
                            question_line = line.strip()
                            break
                # 6. Extract from inside code blocks (triple backticks) as fallback
                if not question_line:
                    in_code = False
                    for line in lines:
                        if line.startswith('```'):
                            in_code = not in_code
                            continue
                        if in_code and line and line != '```' and not line.startswith('|im_start|') and not re.match(r"^next question[:\- ]*", line, re.IGNORECASE):
                            # Strip quotes if present
                            q = line.strip('"\'')
                            if q and q != '```':
                                question_line = q
                                break
                # 7. Fallback: first line with a question mark
                if not question_line:
                    for line in lines:
                        if line and line != '```' and '?' in line:
                            question_line = line.strip()
                            break
                # 8. Fallback: first non-meta, non-empty, non-code-block line
                if not question_line:
                    for line in lines:
                        line_stripped = line.strip() if line else ''
                        if line_stripped and line_stripped != '```' and not re.match(r"^next question[:\- ]*", line_stripped, re.IGNORECASE) and not line_stripped.startswith("```") and not line_stripped.startswith("|im_start|"):
                            question_line = line_stripped
                            break
                if question_line:
                    ai_response = question_line
                else:
                    ai_response = "Sorry, I glitched. Please try again."

                return ai_response

            except ClientError as e:
                print(f"[ERROR] Bedrock ClientError: {str(e)}")
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                print(f"[ERROR] Error code: {error_code}")
                return self._get_fallback_response(current_step, formatted_context)

        except Exception as e:
            print(f"[ERROR] Error in process_visitor_input: {str(e)}")
            return self._get_fallback_response(current_step, formatted_context)

    def process_guest_input(self, user_input: str, current_step: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process guest input with enhanced context awareness"""
        context['interaction_count'] = context.get('interaction_count', 0) + 1
        
        # Validate input based on current step
        is_valid, error_msg = validate_with_context(
            current_step, 
            user_input, 
            self.response_context
        )
        
        if not is_valid:
            context['is_error'] = True
            return {
                'status': 'error',
                'message': error_msg,
                'next_step': current_step  # Stay on current step
            }
            
        # Update context and move to next step
        context[current_step] = user_input
        context['is_error'] = False
        next_step = self.get_next_step(current_step)
        
        # Generate dynamic response
        response = {
            'status': 'success',
            'message': self.get_dynamic_step_prompt(next_step, context),
            'next_step': next_step
        }
        
        # Add personality to successful transitions
        if next_step != current_step:
            response['message'] = self.add_personality_to_response(
                response['message'],
                context
            )
            
        return response
        
    def add_personality_to_response(self, message: str, context: Dict[str, Any]) -> str:
        """Add REBEL personality to responses based on context"""
        # Add encouraging phrases for progress
        progress_phrases = [
            "You're crushing it! ",
            "Perfect! ",
            "Looking good! ",
            "Awesome! ",
            "That's the spirit! "
        ]
        
        # Don't overuse personality phrases
        if context.get('interaction_count', 0) % 2 == 0:
            message = f"{random.choice(progress_phrases)}{message}"
            
        return message
        
    def get_next_step(self, current_step: str) -> str:
        """Determine next step in guest flow"""
        step_order = ['name', 'cnic', 'phone', 'host', 'purpose', 'confirm']
        try:
            current_index = step_order.index(current_step)
            return step_order[current_index + 1]
        except (ValueError, IndexError):
            return 'confirm'  # Default to confirm if something goes wrong

    def _get_fallback_response(self, step: str, context: Dict[str, Any]) -> str:
        """Get a fallback response when AI fails, with REBEL personality for guest flow"""
        name = context.get("visitor_name", "")
        name_greeting = f", {name}" if name else ""
        flow_type = context.get("visitor_type", "guest")
        validation_error = context.get("validation_error", "")
        member_num = context.get("member_number")
        is_repeated = context.get("is_repeated_error", False)
        
        # Use dynamic prompt for fallback
        prompt = get_dynamic_prompt(step, flow_type)
        if name:
            prompt = f"{name}, {prompt.lower()}"
        return prompt or "Sorry, something went wrong. Please try again or contact reception."

    def get_system_account_token(self) -> str:
        """Get an access token using delegated auth flow."""
        if not self.auth_manager:
            raise Exception("AuthManager not initialized. Please ensure auth_manager is provided during initialization.")
        token = self.auth_manager.get_valid_token()
        if not token:
            logger.error("No valid token found - admin needs to authenticate")
            raise Exception("Not authenticated. Admin needs to log in.")
        return token

    async def get_user_id(self, email: str, access_token: str) -> str:
        """Get a user's Object ID from their email using Microsoft Graph API."""
        if not email or not access_token:
            raise ValueError("Email and access token are required")

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # Use filter to get exact match on email
        url = f"https://graph.microsoft.com/v1.0/users?$filter=mail eq '{email}' or userPrincipalName eq '{email}'"
        
        try:
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                print(f"Error getting user ID: {response.status_code} {response.text}")
                raise Exception(f"Failed to get user ID: {response.text}")
                
            data = response.json()
            users = data.get('value', [])
            
            if not users:
                raise Exception(f"No user found with email {email}")
                
            # Return the object ID of the first matching user
            return users[0]['id']
            
        except Exception as e:
            print(f"Error in get_user: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def create_or_get_chat(self, host_user_id: str, system_user_id: str, access_token: str) -> Optional[str]:
        """Create or get an existing chat between the host and the system account."""
        logger.info(f"[DEBUG] create_or_get_chat called with host_user_id={host_user_id}, system_user_id={system_user_id}")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # First, try to find an existing 1:1 chat
        url = f"https://graph.microsoft.com/v1.0/chats"
        # Retry logic for transient errors
        for attempt in range(3):
            try:
                logger.info(f"[DEBUG] Attempt {attempt+1} to get existing chat...")
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, headers=headers)
                    if response.status_code == 503:
                        logger.warning(f"[RETRY] 503 Service Unavailable on attempt {attempt+1}")
                        await asyncio.sleep(2)
                        continue
                    if response.status_code != 200:
                        logger.error(f"Failed to fetch chats: {response.status_code} {response.text}")
                        return None
                    chat_response = response.json()
                    logger.debug(f"[DEBUG] Chat response: {chat_response}")
                    chat_list = chat_response.get("value", [])
                    if not isinstance(chat_list, list):
                        logger.error("Unexpected format in chat response: 'value' is not a list")
                        chat_list = []
                    # Try to find existing chat
                    for chat in chat_list:
                        if chat.get("chatType") != "oneOnOne":
                            continue
                        chat_id = chat.get("id")
                        if not chat_id:
                            continue
                        members_url = f"https://graph.microsoft.com/v1.0/chats/{chat_id}/members"
                        members_resp = await client.get(members_url, headers=headers)
                        if members_resp.status_code != 200:
                            logger.warning(f"Failed to fetch members for chat {chat_id}: {members_resp.status_code} {members_resp.text}")
                            continue
                        members_data = members_resp.json()
                        logger.debug(f"[DEBUG] Members for chat {chat_id}: {members_data}")
                        members = members_data.get("value", [])
                        if not isinstance(members, list):
                            logger.warning(f"Unexpected members format for chat {chat_id}")
                            continue
                        member_ids = [m.get("userId") for m in members if m.get("userId")]
                        if set(member_ids) == set([system_user_id, host_user_id]):
                            logger.info(f"[DEBUG] Found existing 1:1 chat with ID: {chat_id}")
                            return chat_id
                    logger.debug("No existing chat found. Creating new chat...")
                    # Create new 1:1 chat
                    create_url = "https://graph.microsoft.com/v1.0/chats"
                    body = {
                        "chatType": "oneOnOne",
                        "members": [
                            {
                                "@odata.type": "#microsoft.graph.aadUserConversationMember",
                                "roles": ["owner"],
                                "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{system_user_id}')"
                            },
                            {
                                "@odata.type": "#microsoft.graph.aadUserConversationMember",
                                "roles": ["owner"],
                                "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{host_user_id}')"
                            }
                        ]
                    }
                    create_resp = await client.post(create_url, headers=headers, json=body)
                    if create_resp.status_code == 503:
                        logger.warning(f"[RETRY] 503 Service Unavailable on chat create, attempt {attempt+1}")
                        await asyncio.sleep(2)
                        continue
                    if create_resp.status_code in (200, 201):
                        chat_id = create_resp.json().get("id")
                        logger.debug(f"Created new chat with ID: {chat_id}")
                        return chat_id
                    else:
                        logger.error(f"Failed to create new chat: {create_resp.status_code} {create_resp.text}")
                        return None
            except Exception as e:
                logger.error(f"[ERROR] Failed to create or get chat (attempt {attempt+1}): {str(e)}")
                await asyncio.sleep(2)
        logger.error("[ERROR] All attempts to create or get chat failed.")
        return None

    async def send_message_to_host(self, chat_id: str, access_token: str, message: str):
        logger.info(f"[DEBUG] send_message_to_host called with chat_id={chat_id}, message={message}")
        try:
            # Prepare the message payload for Graph API
            url = f"https://graph.microsoft.com/v1.0/chats/{chat_id}/messages"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            body = {
                "body": {
                    "contentType": "html",  # <-- Send as HTML for Teams formatting
                    "content": message
                }
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=body)
                if response.status_code not in (200, 201):
                    logger.error(f"[ERROR] Failed to send message to host: {response.status_code} {response.text}")
                    raise Exception(f"Failed to send message: {response.text}")
                logger.info(f"[DEBUG] Message sent to chat_id={chat_id}")
        except Exception as e:
            logger.error(f"[ERROR] Failed to send message to host: {str(e)}")
            raise

    async def schedule_meeting(self, host_email: str, visitor_name: str, visitor_phone: str, purpose: str) -> bool:
        """Schedule a meeting with the host using Microsoft Graph API."""
        try:
            logger.info(f"[DEBUG] schedule_meeting called with host_email={host_email}, visitor_name={visitor_name}, visitor_phone={visitor_phone}, purpose={purpose}")
            access_token = self.auth_manager.get_valid_token()
            logger.info(f"[DEBUG] Acquired access token: {access_token[:10]}..." if access_token else "[DEBUG] No access token acquired")
            if not access_token:
                logger.error("[DEBUG] Failed to acquire access token")
                raise Exception("Failed to acquire access token")

            # Get user IDs for host and system account
            logger.info(f"[DEBUG] Getting user ID for host: {host_email}")
            host_user_id = await self.get_user_id(host_email, access_token)
            logger.info(f"[DEBUG] Got host user ID: {host_user_id}")
            logger.info(f"[DEBUG] Getting user ID for system account: {self._system_account_email}")
            system_user_id = await self.get_user_id(self._system_account_email, access_token)
            logger.info(f"[DEBUG] Got system user ID: {system_user_id}")

            # Create or get chat
            logger.info(f"[DEBUG] Creating/getting chat between {host_user_id} and {system_user_id}...")
            chat_id = await self.create_or_get_chat(host_user_id, system_user_id, access_token)
            logger.info(f"[DEBUG] Got chat ID: {chat_id}")

            if not chat_id:
                logger.error("[ERROR] Could not create or get chat. Teams notification will not be sent.")
                return False

            # Send Teams message
            message = (
                "🚨 <b>Guest Arrival Notification</b><br><br>"
                "A guest has stormed the gates. Here are the details:<br><br>"
                f"👤 Name: {visitor_name}<br>"
                f"📞 Phone: {visitor_phone}"
            )
            # if visitor_cnic := kwargs.get('visitor_cnic'):
            #     message += f"<br>🆔 CNIC: {visitor_cnic}"
            # if purpose := kwargs.get('purpose'):
            #     message += f"<br>🎯 Purpose: {purpose}"
            # if host := kwargs.get('host'):
            #     message += f"<br>🤝 Host: {host}"
            logger.info("[DEBUG] Sending Teams message...")
            await self.send_message_to_host(chat_id, access_token, message)
            logger.info(f"[DEBUG] Teams notification sent successfully to {host_email}")
            return True
        except Exception as e:
            logger.error(f"Error scheduling meeting: {str(e)}")
            return False

    async def get_scheduled_meetings(self, host_email: str, visitor_name: str, check_time: datetime) -> Optional[List[Dict[str, Any]]]:
        """Check host's calendar for all scheduled meetings using Microsoft Graph API (for selection)."""
        try:
            import json
            try:
                from zoneinfo import ZoneInfo  # Python ≥3.9
                try:
                    pk_tz = ZoneInfo("Asia/Karachi")
                except KeyError:
                    raise ImportError  # force fallback if key missing
            except ImportError:
                import pytz
                pk_tz = pytz.timezone("Asia/Karachi")

            # Initialize MSAL client
            app = msal.ConfidentialClientApplication(
                CLIENT_ID,
                authority=f"https://login.microsoftonline.com/{TENANT_ID}",
                client_credential=CLIENT_SECRET,
            )

            # Get token
            result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])

            if "access_token" not in result:
                print("[DEBUG] Could not acquire token")
                return None

            token = result["access_token"]
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            # Ensure check_time is timezone-aware UTC
            if check_time.tzinfo is None:
                check_time = check_time.replace(tzinfo=timezone.utc)

            # Convert check_time to Pakistan time correctly
            check_time_pk = check_time.astimezone(pk_tz)
            # Get PKT start/end of day
            start_of_day_pk = check_time_pk.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day_pk = check_time_pk.replace(hour=23, minute=59, second=59, microsecond=999999)
            # Convert back to UTC for API call
            start_of_day_utc = start_of_day_pk.astimezone(timezone.utc)
            end_of_day_utc = end_of_day_pk.astimezone(timezone.utc)

            # Format times for Microsoft Graph API
            start_time = start_of_day_utc.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            end_time = end_of_day_utc.strftime('%Y-%m-%dT%H:%M:%S.999Z')

            # Prepare calendar API call
            url = (
                f"https://graph.microsoft.com/v1.0/users/{host_email}/calendar/calendarView"
                f"?startDateTime={start_time}&endDateTime={end_time}"
                f"&$orderby=start/dateTime&$top=20"
            )

            print(f"[DEBUG] Host email: {host_email}")
            print(f"[DEBUG] Querying from {start_time} to {end_time} (UTC)")
            print(f"[DEBUG] CalendarView URL: {url}")

            response = requests.get(url, headers=headers)

            print(f"[DEBUG] Response status: {response.status_code}")
            try:
                print(f"[DEBUG] Response JSON: {json.dumps(response.json(), indent=2)}")
            except Exception as e:
                print(f"[ERROR] Could not parse JSON: {e}")

            if response.status_code == 200:
                events = response.json().get("value", [])
                meetings = []
                for event in events:
                    # Skip cancelled events
                    if event.get("isCancelled", False):
                        print(f"[DEBUG] Skipping cancelled event: {event.get('subject')}")
                        continue
                        
                    start = event.get("start", {}).get("dateTime")
                    end = event.get("end", {}).get("dateTime")
                    if start and end:
                        # Convert times to datetime objects for proper handling
                        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                        # Ensure both are timezone-aware (UTC)
                        if start_dt.tzinfo is None:
                            start_dt = start_dt.replace(tzinfo=timezone.utc)
                        if end_dt.tzinfo is None:
                            end_dt = end_dt.replace(tzinfo=timezone.utc)
                        # Add all meetings of the day, regardless of whether they are in the past or future
                        meeting = {
                            "scheduled_time": start,
                            "end_time": end,
                            "purpose": event.get("subject", "Pre-scheduled meeting"),
                            "original_event": event
                        }
                        meetings.append(meeting)
                        print(f"[DEBUG] Added meeting: {meeting['purpose']} at {meeting['scheduled_time']}")
                
                print(f"[DEBUG] Total meetings found: {len(meetings)}")
                for m in meetings:
                    print(f"  → {m['scheduled_time']} to {m['end_time']}: {m['purpose']}")
                
                if not meetings:
                    print("[DEBUG] No valid meetings found")
                    return None
                    
                return meetings
            else:
                print(f"[ERROR] Error fetching calendar events: {response.status_code}")
                print(f"[ERROR] Response text: {response.text}")
                return None
        except Exception as e:
            print(f"[ERROR] Error checking calendar: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    async def handle_employee_selection(self, user_input: str, employee_matches: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Handle employee selection from a list of matches"""
        print(f"[DEBUG] Processing employee selection input: {user_input}")
        print(f"[DEBUG] Available matches: {len(employee_matches)} employees")
        
        if not employee_matches:
            print("[DEBUG] No employee matches available")
            return None
            
        try:
            if user_input.isdigit():
                selection = int(user_input)
                print(f"[DEBUG] User selected number: {selection}")
                
                if selection == 0:
                    print("[DEBUG] User chose to enter a different name")
                    return None
                    
                if 1 <= selection <= len(employee_matches):
                    selected = employee_matches[selection - 1]
                    print(f"[DEBUG] Selected employee: {selected['displayName']}")
                    print(f"[DEBUG] Employee email: {selected.get('email', 'No email')}")
                    print(f"[DEBUG] Employee department: {selected.get('department', 'Unknown Department')}")
                    return selected
                else:
                    print(f"[DEBUG] Invalid selection number: {selection} (valid range: 1-{len(employee_matches)})")
            else:
                print(f"[DEBUG] Invalid input: {user_input} (expected a number)")
                
            return None
        except Exception as e:
            print(f"[ERROR] Error in handle_employee_selection: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def _refresh_delegated_token(self, refresh_token: str = None) -> Optional[dict]:
        """Refresh a delegated token using either the refresh token or getting a new one from auth manager."""
        try:
            # First try to get a new token from auth manager
            if self.auth_manager:
                token = self.auth_manager.get_valid_token()
                token_info = self.auth_manager.get_token_info()
                if token and token_info:
                    return token_info
            
            # If that fails and we have a refresh token, try using it
            if refresh_token:
                token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
                data = {
                    "client_id": CLIENT_ID,
                    "scope": "Chat.ReadWrite User.Read Calendars.ReadWrite",  # Space-separated delegated scopes
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                    "client_secret": CLIENT_SECRET,
                }
                resp = requests.post(token_url, data=data)
                if resp.status_code == 200:
                    return resp.json()
            return None
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return None

    def _cache_delegated_token(self, token_info: dict):
        """Cache a delegated token with its expiry and refresh token."""
        with self._token_lock:
            self._token_cache = {
                'access_token': token_info['access_token'],
                'refresh_token': token_info.get('refresh_token'),
                'expires_at': time.time() + token_info.get('expires_in', 3600)
            }
    
def call_bedrock_with_retries(client, model_id, payload, max_retries=8):
    import time
    import botocore.exceptions
    for attempt in range(max_retries):
        try:
            return client.invoke_model(
                modelId=model_id,
                body=payload,
                accept="application/json",
                contentType="application/json"
            )
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'ThrottlingException':
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"[WARN] ThrottlingException: retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                raise e
    raise Exception("Exceeded maximum retries for Bedrock model")