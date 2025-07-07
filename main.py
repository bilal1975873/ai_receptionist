import os
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

import asyncio
from ai_integration import AIReceptionist
from flows import (guest_flow, SUPPLIERS, vendor_flow, validate_cnic, validate_phone, validate_name, validate_email,
                  validate_group_size, validate_with_context)
from prompts import get_dynamic_prompt, get_confirmation_message, get_error_message, HARDCODED_WELCOME, SUPPLIERS
import random
from prescheduled_flow import PreScheduledFlow

# --- FastAPI & MongoDB Integration ---
from fastapi import FastAPI, HTTPException, Request, Depends, status, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2AuthorizationCodeBearer
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Literal
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone, timedelta
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
from jose import JWTError, jwt
from client_config import ClientConfig
import requests
import time
import json
from auth import router as auth_router, is_logged_in
from auth_utils import get_valid_tokens, log
from contextlib import asynccontextmanager

# Initialize application
app = FastAPI()

# Initialize AI receptionist
ai_receptionist = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize AI receptionist with auth manager
    global ai_receptionist
    from ai_integration import AuthManager  # Import AuthManager from ai_integration
    auth_manager = AuthManager()  # Create an instance of AuthManager
    ai_receptionist = AIReceptionist(auth_manager=auth_manager)  # Pass auth_manager to AIReceptionist
    await ai_receptionist.initialize()
    yield
    # Shutdown: Clean up if needed
    ai_receptionist = None

app = FastAPI(lifespan=lifespan)

# Session middleware must be added FIRST
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "ffsdfjsdkfjsdahfoiahfuhufoeihfo"),
    session_cookie="dpl_session",
    max_age=86400,
    same_site="lax",
    https_only=False, # Set to True in production
    path="/",
)

# CORS middleware with proper configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include auth router with proper prefix and tags
app.include_router(
    auth_router,
    prefix="/auth",
    tags=["authentication"],
    include_in_schema=True
)

# Load environment variables
load_dotenv()

# Get Azure AD credentials
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TENANT_ID = os.getenv("TENANT_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8000/auth/callback")

if not all([CLIENT_ID, CLIENT_SECRET, TENANT_ID]):
    raise ValueError("Missing required Azure AD environment variables (CLIENT_ID, CLIENT_SECRET, TENANT_ID)")

# OAuth2 configuration with delegated permissions
auth_config = {
    'client_id': CLIENT_ID,
    'client_secret': CLIENT_SECRET,
    'auth_uri': f'https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/authorize',
    'token_uri': f'https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token',
    'scope': [
        'openid',
        'profile',
        'email',
        'Chat.ReadWrite',
        'Chat.Create',
        'User.Read',
        'Calendars.ReadWrite'
    ],
    'redirect_uri': REDIRECT_URI,
}

oauth = OAuth()
oauth.register(
    name='azure',
    server_metadata_url=f'https://login.microsoftonline.com/{TENANT_ID}/v2.0/.well-known/openid-configuration',
    client_id=auth_config['client_id'],
    client_secret=auth_config['client_secret'],
    client_kwargs={'scope': ' '.join(auth_config['scope'])}
)

# JWT Settings
SECRET_KEY = os.getenv("SECRET_KEY", os.urandom(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Load environment variables
load_dotenv()

# MongoDB Atlas setup
MONGODB_URI = os.getenv("MONGODB_URI")
if not MONGODB_URI:
    raise ValueError("MONGODB_URI environment variable is not set")

# Initialize MongoDB client
client = AsyncIOMotorClient(MONGODB_URI)
db = client.get_default_database()
visitors_collection = db["visitors"]

# Add OAuth2 and JWT configuration
oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"https://login.microsoftonline.com/{os.getenv('TENANT_ID')}/oauth2/v2.0/authorize",
    tokenUrl=f"https://login.microsoftonline.com/{os.getenv('TENANT_ID')}/oauth2/v2.0/token"
)

# JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY", os.urandom(32).hex())
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Session middleware already added above
# Removing duplicate session middleware configuration

# Authentication models
class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict

class TokenData(BaseModel):
    username: Optional[str] = None

# Authentication utility functions
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    return token_data

# Authentication routes are handled in auth.py

# Logout endpoint is handled in auth.py

@app.get("/protected")
async def protected(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/auth/login")
    return {"message": "You are logged in!", "user": request.session.get("access_token")}

@app.get("/protected")
async def protected_route(current_user: TokenData = Depends(get_current_user)):
    return {"message": "This is a protected route", "user": current_user.username}

# Pydantic Visitor model
class Visitor(BaseModel):
    type: Literal['guest', 'vendor']
    full_name: str
    cnic: Optional[str] = None
    phone: str
    email: Optional[str] = None
    host: str
    purpose: str
    entry_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    exit_time: Optional[datetime] = None
    is_group_visit: bool = False
    group_id: Optional[str] = None
    total_members: int = 1
    group_members: list = []

# MongoDB error handler
async def handle_db_operation(operation):
    try:
        return await operation
    except Exception as e:
        print(f"MongoDB operation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Database operation failed: {str(e)}"
        )

@app.post("/visitors/", response_model=Visitor)
async def create_visitor(visitor: Visitor):
    data = visitor.dict()
    result = await handle_db_operation(visitors_collection.insert_one(data))
    if not result.acknowledged:
        raise HTTPException(status_code=500, detail="Failed to insert visitor.")
    data["_id"] = str(result.inserted_id)
    return visitor

@app.get("/visitors/", response_model=list[Visitor])
async def list_visitors():
    visitors = []
    cursor = visitors_collection.find()
    async for visitor in cursor:
        visitor["_id"] = str(visitor["_id"])
        visitors.append(visitor)
    return visitors

@app.get("/visitors/{cnic}", response_model=Visitor)
async def get_visitor(cnic: str):
    visitor = await handle_db_operation(visitors_collection.find_one({"cnic": cnic}))
    if not visitor:
        raise HTTPException(status_code=404, detail="Visitor not found.")
    visitor["_id"] = str(visitor["_id"])
    return Visitor(**visitor)

@app.put("/visitors/{cnic}", response_model=Visitor)
async def update_visitor(cnic: str, update: Visitor):
    result = await handle_db_operation(
        visitors_collection.update_one({"cnic": cnic}, {"$set": update.dict()})
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Visitor not found.")
    return update

@app.delete("/visitors/{cnic}")
async def delete_visitor(cnic: str):
    result = await handle_db_operation(visitors_collection.delete_one({"cnic": cnic}))
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Visitor not found.")
    return {"detail": "Visitor deleted."}

async def insert_visitor_to_db(visitor_type, full_name, cnic, phone, host, purpose, is_group_visit=False, group_members=None, total_members=1, email=None):
    entry_time = datetime.now(timezone.utc)
    group_id = None
   
    if is_group_visit:
        group_id = str(datetime.now(timezone.utc).timestamp())

    visitor_doc = {
        "type": visitor_type,
        "full_name": full_name,
        "cnic": cnic,
        "phone": phone,
        "email": email,  # Added email field
        "host": host,
        "purpose": purpose,
        "entry_time": entry_time,
        "exit_time": None,
        "is_group_visit": is_group_visit,
        "group_id": group_id,
        "total_members": total_members,
        "group_members": group_members or []
    }
    await visitors_collection.insert_one(visitor_doc)

class VisitorInfo:
    def __init__(self):
        self.visitor_type = None
        self.visitor_name = None
        self.visitor_cnic = None
        self.visitor_phone = None
        self.host_requested = None
        self.host_confirmed = None
        self.host_email = None
        self.purpose = None
        self.verification_status = None
        self.supplier = None  # For vendor flow
        self.group_id = None  # For group visits
        self.is_group_visit = False
        self.group_members = []  # List to store additional visitors
        self.total_members = 1  # Default to 1, will be updated for groups
       
    def to_dict(self):
        return {
            "visitor_type": self.visitor_type,
            "visitor_name": self.visitor_name,
            "visitor_cnic": self.visitor_cnic,
            "visitor_phone": self.visitor_phone,
            "host_requested": self.host_requested,
            "host_confirmed": self.host_confirmed,
            "host_email": self.host_email,
            "purpose": self.purpose,
            "verification_status": self.verification_status,
            "supplier": self.supplier,
            "group_id": self.group_id,
            "is_group_visit": self.is_group_visit,
            "total_members": self.total_members,
            "group_members": self.group_members
        }
   
    def summary(self):
        lines = ["=== Visitor Information Summary ==="]
        if self.visitor_name:
            lines.append(f"Name: {self.visitor_name}")
        if self.visitor_cnic:
            lines.append(f"CNIC: {self.visitor_cnic}")
        if self.visitor_phone:
            lines.append(f"Phone: {self.visitor_phone}")
        if self.host_confirmed:
            lines.append(f"Host: {self.host_confirmed}")
        if self.purpose:
            lines.append(f"Purpose: {self.purpose}")
        return "\n".join(lines)

class DPLReceptionist:
    def __init__(self, ai=None):
        self.visitor_info = VisitorInfo()
        self.ai = ai if ai is not None else AIReceptionist()
        self.current_step = "visitor_type"
        self.employee_selection_mode = False
        self.employee_matches = []
        from flows import ResponseContext
        self.response_context = ResponseContext()
       
    def reset(self):
        self.init()
       
    async def process_input(self, user_input: str) -> str:
        # Handle visitor type selection (only at the very start)
        if self.current_step == "visitor_type":
            user_input = user_input.lower().strip()
            context = {"current_step": "visitor_type", **self.visitor_info.to_dict()}

            # Handle invalid input before trying AI response
            if not user_input:
                return "Please select: 1 for Guest, 2 for Vendor, 3 for Pre-scheduled meeting"

            # Only call AI once, after logic
            if user_input in ["1", "guest"]:
                self.visitor_info.visitor_type = "guest"
                self.current_step = "name"
                context = {"current_step": self.current_step, **self.visitor_info.to_dict()}
                return await self.get_ai_response(user_input, context)
            elif user_input in ["2", "vendor"]:
                self.visitor_info.visitor_type = "vendor"
                self.current_step = "supplier"
                context = {"current_step": self.current_step, **self.visitor_info.to_dict()}
                supplier_list = "\n".join(f"{idx}. {supplier}" for idx, supplier in enumerate(SUPPLIERS, 1))
                ai_msg = await self.get_ai_response(user_input, context)
                return f"{ai_msg or get_dynamic_prompt('supplier', 'vendor')}\n\n{supplier_list}"
            elif user_input in ["3", "prescheduled", "pre-scheduled", "pre scheduled", "i have a pre-scheduled meeting"]:
                self.visitor_info.visitor_type = "prescheduled"
                self.current_step = "scheduled_name"
                return "Please enter your name."
            else:
                # Return standard error message for invalid input
                return get_error_message("visitor_type")

        # Guest flow (all responses must be AI-generated)
        if self.visitor_info.visitor_type == "guest":
            steps = guest_flow["steps"]
            step_idx = steps.index(self.current_step) if self.current_step in steps else 0
            context = {"current_step": self.current_step, **self.visitor_info.to_dict()}

            if self.current_step == "name":
                if not user_input.strip():
                    return get_error_message("empty_field")
                if not validate_name(user_input.strip()):
                    return get_error_message("name_invalid")
                self.visitor_info.visitor_name = user_input.strip()
                self.current_step = "cnic"
                context = {"current_step": self.current_step, **self.visitor_info.to_dict()}
                # Always use AI-generated prompt for guest flow questions
                return await self.get_ai_response(user_input, context)

            elif self.current_step == "cnic":
                is_valid, error_msg = validate_with_context("cnic", user_input.strip(), self.response_context)
                if not is_valid:
                    return get_error_message("cnic_invalid")
                self.visitor_info.visitor_cnic = user_input.strip()
                self.current_step = "phone"
                context = {"current_step": self.current_step, **self.visitor_info.to_dict()}
                return await self.get_ai_response(user_input, context)

            elif self.current_step == "phone":
                is_valid, error_msg = validate_with_context("phone", user_input.strip(), self.response_context)
                if not is_valid:
                    return get_error_message("phone_invalid")
                self.visitor_info.visitor_phone = user_input.strip()
                self.current_step = "host"
                context = {"current_step": self.current_step, **self.visitor_info.to_dict()}
                return await self.get_ai_response(user_input, context)

            elif self.current_step == "host":
                if self.employee_selection_mode:
                    if user_input.strip() == "0" or user_input.lower() == "none of these" or user_input.lower() == "none of these / enter a different name":
                        self.employee_selection_mode = False
                        self.employee_matches = []
                        return "Please enter a different name."
                    if user_input.isdigit():
                        index = int(user_input) - 1
                        if 0 <= index < len(self.employee_matches):
                            selected_employee = self.employee_matches[index]
                        else:
                            selected_employee = None
                    else:
                        # If it's not a number, treat as a fresh host search
                        self.employee_selection_mode = False
                        self.employee_matches = []
                        self.current_step = "host"
                        return await self._run_guest_host_step(user_input)
                    if selected_employee:
                        # Store host information
                        host_name = selected_employee["displayName"]
                        host_email = selected_employee["email"]
                        
                        # Update all host-related fields
                        self.visitor_info.host_confirmed = host_name
                        self.visitor_info.host_email = host_email
                        self.visitor_info.host_requested = host_name  # Also store as host_requested as backup
                        
                        # Detailed debug logging
                        print(f"[DEBUG] Host selected and stored in visitor_info:")
                        print(f"[DEBUG]   - host_confirmed: {self.visitor_info.host_confirmed}")
                        print(f"[DEBUG]   - host_email: {self.visitor_info.host_email}")
                        print(f"[DEBUG]   - host_requested: {self.visitor_info.host_requested}")
                        
                        # Update state
                        self.employee_selection_mode = False
                        self.employee_matches = []
                        self.current_step = "purpose"
                        
                        # Make sure all host info is included in context
                        context = {
                            "current_step": self.current_step,
                            **self.visitor_info.to_dict(),
                            "host_confirmed": host_name,
                            "host_email": host_email,
                            "host_requested": host_name  # Include in context as well
                        }
                        # return get_dynamic_prompt("purpose", "guest")
                        return await self.get_ai_response(user_input, context)
                    else:
                        options = "Please select one of these names:\n"
                        for emp in self.employee_matches:
                            dept = emp.get("department", "Unknown Department")
                            options += f"{emp['displayName']} ({dept})\n"
                        options += "None of these / Enter a different name"
                        return options
                else:
                    if user_input.strip() == "0" or user_input.strip().lower().startswith("none of these"):
                        self.employee_selection_mode = False
                        self.employee_matches = []
                        return "Please enter a different name."
                    employee = await self.ai.search_employee(user_input)
                    if isinstance(employee, dict):
                        self.employee_selection_mode = True
                        self.employee_matches = [employee]
                        options = "I found the following match. Please select by number:\n"
                        dept = employee.get("department", "Unknown Department")
                        options += f"  1. {employee['displayName']} ({dept})\n"
                        options += "  0. None of these / Enter a different name"
                        return options
                    elif isinstance(employee, list):
                        self.employee_selection_mode = True
                        self.employee_matches = employee
                        options = "I found multiple potential matches. Please select one:\n"
                        for i, emp in enumerate(employee, 1):
                            dept = emp.get("department", "Unknown Department")
                            options += f"  {i}. {emp['displayName']} ({dept})\n"
                        options += "  0. None of these / Enter a different name"
                        return options
                    else:
                        return "No matches found. Please enter a different name."

            elif self.current_step == "purpose":
                if not user_input.strip():
                    return get_error_message("empty_field")
                self.visitor_info.purpose = user_input.strip()
                self.current_step = "confirm"
                context = {"current_step": self.current_step, **self.visitor_info.to_dict()}
                # Confirmation is not a question, so keep as is
                summary = f"Name: {self.visitor_info.visitor_name}\nCNIC: {self.visitor_info.visitor_cnic}\nPhone: {self.visitor_info.visitor_phone}"
                if self.visitor_info.host_confirmed:
                    summary += f"\nHost: {self.visitor_info.host_confirmed}"
                if self.visitor_info.purpose:
                    summary += f"\nPurpose: {self.visitor_info.purpose}"
                confirm_msg = get_confirmation_message().format(details=summary)
                return confirm_msg

            elif self.current_step == "confirm":
                summary = f"Name: {self.visitor_info.visitor_name}\nCNIC: {self.visitor_info.visitor_cnic}\nPhone: {self.visitor_info.visitor_phone}"
                if self.visitor_info.host_confirmed:
                    summary += f"\nHost: {self.visitor_info.host_confirmed}"
                if self.visitor_info.purpose:
                    summary += f"\nPurpose: {self.visitor_info.purpose}"
                confirm_msg = get_confirmation_message().format(details=summary)
                if user_input.lower() == "confirm":
                    self.current_step = "complete"
                    print(f"[DEBUG] Saving guest: host_confirmed={self.visitor_info.host_confirmed}")
                    # Handle host name with detailed logging
                    host_name = None
                    
                    # Try host_confirmed first
                    if self.visitor_info.host_confirmed:
                        host_name = self.visitor_info.host_confirmed
                        print(f"[DEBUG] Using host_confirmed: {host_name}")
                    
                    # Fall back to host_requested if needed
                    elif self.visitor_info.host_requested:
                        host_name = self.visitor_info.host_requested
                        print(f"[DEBUG] Using host_requested as fallback: {host_name}")
                    
                    # Final fallback
                    if not host_name:
                        print("[WARN] No host name found in either host_confirmed or host_requested")
                        host_name = ""
                    
                    print(f"[DEBUG] Final host name for database: {host_name}")
                    
                    # Save to database
                    await insert_visitor_to_db(
                        visitor_type=self.visitor_info.visitor_type or "guest",
                        full_name=self.visitor_info.visitor_name or "",
                        cnic=self.visitor_info.visitor_cnic or "",
                        phone=self.visitor_info.visitor_phone or "",
                        host=host_name,
                        purpose=self.visitor_info.purpose or "",
                        is_group_visit=self.visitor_info.is_group_visit,
                        group_members=self.visitor_info.group_members,
                        total_members=self.visitor_info.total_members
                    )
                    try:
                        if self.ai.graph_client is not None:
                            await self.ai.schedule_meeting(
                                self.visitor_info.host_email,
                                self.visitor_info.visitor_name,
                                self.visitor_info.visitor_phone,
                                self.visitor_info.purpose
                            )
                    except Exception as e:
                        print(f"Error scheduling meeting: {e}")
                    context = {"current_step": self.current_step, **self.visitor_info.to_dict()}
                    return await self.get_ai_response(user_input, context)
                elif user_input.lower() == "edit":
                    self.current_step = "name"
                    context = {"current_step": self.current_step, **self.visitor_info.to_dict()}
                    return await self.get_ai_response(user_input, context)
                else:
                    return confirm_msg

            elif self.current_step == "complete":
                # Set registration_completed for frontend
                context = {"current_step": self.current_step, **self.visitor_info.to_dict()}
                context["registration_completed"] = True
                return "Registration successful. Rebel presence incoming — host’s been warned."

        # Vendor flow (strict, only hardcoded prompts, strict step order)
        if self.visitor_info.visitor_type == "vendor":
            if self.current_step == "supplier":
                context = {
                    "current_step": self.current_step,
                    **self.visitor_info.to_dict()
                }
                supplier_list = "\n".join(f"{idx}. {supplier}" for idx, supplier in enumerate(SUPPLIERS, 1))
                if user_input.isdigit() and 1 <= int(user_input) <= len(SUPPLIERS):
                    selected = SUPPLIERS[int(user_input) - 1]
                    if selected == "Other":
                        self.current_step = "supplier_other"
                        context = {"current_step": self.current_step, **self.visitor_info.to_dict()}
                        return get_dynamic_prompt("supplier_other", "vendor")
                    else:
                        self.visitor_info.supplier = selected
                        self.current_step = "vendor_name"
                        context = {"current_step": self.current_step, **self.visitor_info.to_dict()}
                        return get_dynamic_prompt("vendor_name", "vendor")
                elif user_input.strip() in SUPPLIERS:
                    if user_input.strip() == "Other":
                        self.current_step = "supplier_other"
                        context = {"current_step": self.current_step, **self.visitor_info.to_dict()}
                        return get_dynamic_prompt("supplier_other", "vendor")
                    else:
                        self.visitor_info.supplier = user_input.strip()
                        self.current_step = "vendor_name"
                        context = {"current_step": self.current_step, **self.visitor_info.to_dict()}
                        return get_dynamic_prompt("vendor_name", "vendor")
                else:
                    ai_msg = await self.get_ai_response(user_input, {**context, "validation_error": "invalid_supplier"})
                    return f"{ai_msg or get_dynamic_prompt('supplier', 'vendor')}\n{supplier_list}"
            elif self.current_step == "supplier_other":
                context = {"current_step": self.current_step, **self.visitor_info.to_dict()}
                if not user_input.strip():
                    return get_error_message("empty_field")
                self.visitor_info.supplier = user_input.strip()
                self.current_step = "vendor_name"
                context["current_step"] = self.current_step
                return get_dynamic_prompt("vendor_name", "vendor")
            elif self.current_step == "vendor_name":
                context = {"current_step": self.current_step, **self.visitor_info.to_dict()}
                if not user_input.strip():
                    return get_error_message("empty_field")
                if not validate_name(user_input.strip()):
                    return get_error_message("name")
                self.visitor_info.visitor_name = user_input.strip()
                self.current_step = "vendor_group_size"
                context["current_step"] = self.current_step
                return get_dynamic_prompt("vendor_group_size", "vendor")
            elif self.current_step == "vendor_group_size":
                context = {"current_step": self.current_step, **self.visitor_info.to_dict()}
                try:
                    group_size = int(user_input.strip())
                    if group_size < 1:
                        return get_error_message("invalid_choice")
                    if group_size > 10:
                        return get_error_message("invalid_choice")
                    self.visitor_info.total_members = group_size
                    self.visitor_info.is_group_visit = group_size > 1
                    if group_size > 1:
                        self.visitor_info.group_id = str(datetime.now(timezone.utc).timestamp())
                    self.current_step = "vendor_cnic"
                    context["current_step"] = self.current_step
                    return get_dynamic_prompt("vendor_cnic", "vendor")
                except ValueError:
                    return get_error_message("invalid_choice")
            elif self.current_step == "vendor_cnic":
                context = {"current_step": self.current_step, **self.visitor_info.to_dict()}
                if not validate_cnic(user_input.strip()):
                    return get_error_message("cnic_invalid")
                self.visitor_info.visitor_cnic = user_input.strip()
                self.current_step = "vendor_phone"
                context["current_step"] = self.current_step
                return get_dynamic_prompt("vendor_phone", "vendor")
            elif self.current_step == "vendor_phone":
                context = {"current_step": self.current_step, **self.visitor_info.to_dict()}
                if not validate_phone(user_input.strip()):
                    return get_error_message("phone_invalid")
                self.visitor_info.visitor_phone = user_input.strip()
                if self.visitor_info.is_group_visit and len(self.visitor_info.group_members) < self.visitor_info.total_members - 1:
                    next_member = len(self.visitor_info.group_members) + 2
                    self.current_step = f"vendor_member_{next_member}_name"
                    context["current_step"] = self.current_step
                    context["next_member"] = next_member
                    return get_dynamic_prompt("vendor_member_name", "vendor").replace("{number}", str(next_member))
                self.current_step = "vendor_confirm"
                context["current_step"] = self.current_step
                summary = f"Supplier: {self.visitor_info.supplier}\nName: {self.visitor_info.visitor_name}\nCNIC: {self.visitor_info.visitor_cnic}\nPhone: {self.visitor_info.visitor_phone}"
                if self.visitor_info.is_group_visit:
                    summary += f"\nGroup size: {self.visitor_info.total_members}"
                    for idx, member in enumerate(self.visitor_info.group_members, 2):
                        summary += f"\nMember {idx}: {member.get('name','')} / {member.get('cnic','')} / {member.get('phone','')}"
                confirm_msg = get_confirmation_message().format(details=summary)
                return confirm_msg
            elif self.current_step.startswith("vendor_member_"):
                parts = self.current_step.split("_")
                member_num = int(parts[2])
                substep = parts[3]
                context = {
                    "current_step": self.current_step,
                    "member_number": member_num,
                    **self.visitor_info.to_dict()
                }
                if substep == "name":
                    if not validate_name(user_input.strip()):
                        return get_error_message("name")
                    self.visitor_info.group_members.append({"name": user_input.strip()})
                    self.current_step = f"vendor_member_{member_num}_cnic"
                    context["current_step"] = self.current_step
                    return get_dynamic_prompt("vendor_member_cnic", "vendor").replace("{number}", str(member_num))
                elif substep == "cnic":
                    if not validate_cnic(user_input.strip()):
                        return get_error_message("cnic_invalid")
                    self.visitor_info.group_members[member_num-2]["cnic"] = user_input.strip()
                    self.current_step = f"vendor_member_{member_num}_phone"
                    context["current_step"] = self.current_step
                    return get_dynamic_prompt("vendor_member_phone", "vendor").replace("{number}", str(member_num))
                elif substep == "phone":
                    if not validate_phone(user_input.strip()):
                        return get_error_message("phone_invalid")
                    self.visitor_info.group_members[member_num-2]["phone"] = user_input.strip()
                    if len(self.visitor_info.group_members) < self.visitor_info.total_members - 1:
                        next_member = len(self.visitor_info.group_members) + 2
                        self.current_step = f"vendor_member_{next_member}_name"
                        context["current_step"] = self.current_step
                        return get_dynamic_prompt("vendor_member_name", "vendor").replace("{number}", str(next_member))
                    else:
                        self.current_step = "vendor_confirm"
                        context["current_step"] = self.current_step
                        summary = f"Supplier: {self.visitor_info.supplier}\nName: {self.visitor_info.visitor_name}\nCNIC: {self.visitor_info.visitor_cnic}\nPhone: {self.visitor_info.visitor_phone}"
                        if self.visitor_info.is_group_visit:
                            summary += f"\nGroup size: {self.visitor_info.total_members}"
                            for idx, member in enumerate(self.visitor_info.group_members, 2):
                                summary += f"\nMember {idx}: {member.get('name','')} / {member.get('cnic','')} / {member.get('phone','')}"
                        confirm_msg = get_confirmation_message().format(details=summary)
                        return confirm_msg
            elif self.current_step == "vendor_confirm":
                context = {"current_step": self.current_step, **self.visitor_info.to_dict()}
                if user_input.lower() in ["yes", "confirm"]:
                    self.current_step = "complete"
                    context["current_step"] = self.current_step
                    await insert_visitor_to_db(
                        visitor_type="vendor",
                        full_name=self.visitor_info.visitor_name or "",
                        cnic=self.visitor_info.visitor_cnic or "",
                        phone=self.visitor_info.visitor_phone or "",
                        host="Admin",
                        purpose=f"Vendor visit - {self.visitor_info.supplier}",
                        is_group_visit=self.visitor_info.is_group_visit,
                        group_members=self.visitor_info.group_members,
                        total_members=self.visitor_info.total_members
                    )
                    try:
                        access_token = self.ai.get_system_account_token()
                        system_user_id = await self.ai.get_user_id("saadsaad@dpl660.onmicrosoft.com", access_token)
                        admin_user_id = await self.ai.get_user_id("admin_IT@dpl660.onmicrosoft.com", access_token)
                        chat_id = await self.ai.create_or_get_chat(admin_user_id, system_user_id, access_token)
                        # --- Use HTML for Teams notification, like pre-scheduled ---
                        message = (
                            "🔔 <b>Vendor Arrival Notification</b><br><br>"
                            "A vendor has arrived at reception. Here are the details:<br><br>"
                            f"👤 Name: {self.visitor_info.visitor_name}<br>"
                            f"🏢 Supplier: {self.visitor_info.supplier}<br>"
                            f"🆔 CNIC: {self.visitor_info.visitor_cnic}<br>"
                            f"📞 Phone: {self.visitor_info.visitor_phone}"
                        )
                        if self.visitor_info.is_group_visit:
                            message += f"<br>👥 Group size: {self.visitor_info.total_members}"
                            for idx, member in enumerate(self.visitor_info.group_members, 2):
                                message += (
    f"<br>Member {idx}:<br>"
    f"&nbsp;&nbsp;👤 Name: {member.get('name','')}<br>"
    f"&nbsp;&nbsp;🆔 CNIC: {member.get('cnic','')}<br>"
    f"&nbsp;&nbsp;📞 Phone: {member.get('phone','')}"
)
                        await self.ai.send_message_to_host(chat_id, access_token, message)
                    except Exception as e:
                        print(f"Error in Teams notification process: {e}")
                    return "Registration successful. Rebel presence incoming — host’s been warned"
                elif user_input.lower() == "edit":
                    self.current_step = "supplier"
                    context["current_step"] = self.current_step
                    supplier_list = "\n".join(f"{idx}. {supplier}" for idx, supplier in enumerate(SUPPLIERS, 1))
                    return f"{get_dynamic_prompt('supplier', 'vendor')}\n{supplier_list}"
                else:
                    summary = f"Supplier: {self.visitor_info.supplier}\nName: {self.visitor_info.visitor_name}\nCNIC: {self.visitor_info.visitor_cnic}\nPhone: {self.visitor_info.visitor_phone}"
                    if self.visitor_info.is_group_visit:
                        summary += f"\nGroup size: {self.visitor_info.total_members}"
                        for idx, member in enumerate(self.visitor_info.group_members, 2):
                            summary += f"\nMember {idx}: {member.get('name','')} / {member.get('cnic','')} / {member.get('phone','')}"
                    confirm_msg = get_confirmation_message().format(details=summary)
                    return confirm_msg
            elif self.current_step == "complete":
                return "Registration successful. Rebel presence incoming — host’s been warned"

        # Generate AI response for the current step
        context = {
            "current_step": self.current_step,
            **self.visitor_info.to_dict()
        }
        return await self.get_ai_response(user_input, context)
   
    async def get_ai_response(self, user_input: str, context: dict) -> str:
        """Get a response from the AI model based on the current context"""
        # Use synchronous version for simplicity
        return self.ai.process_visitor_input(user_input, context)

    async def run(self):
        # Display hardcoded welcome message
        from prompts import HARDCODED_WELCOME
        print(f"\nDPL: {HARDCODED_WELCOME}")
       
        while True:
            if self.current_step == "complete":
                print("DPL: Please wait...")
                await asyncio.sleep(2)  # Give user time to read the completion message
                self.reset()
                print(f"\nDPL: {HARDCODED_WELCOME}")
                continue

            user_input = input("You: ").strip()
            if user_input.lower() in ["quit", "exit"]:
                goodbye_context = {"current_step": "complete", "is_exit": True}
                goodbye_response = self.ai.process_visitor_input("quit", goodbye_context)
                print(f"\nDPL: {goodbye_response}")
                break
           
            response = await self.process_input(user_input)
            print(f"\nDPL: {response}")
           
            # After printing response, if we're in complete state,
            # don't wait for user input before resetting

    async def handle_scheduled_host_step(self, user_input: str) -> str:
        """Handle the host selection step for pre-scheduled meetings"""
        # If in employee selection mode, handle the selection
        if self.employee_selection_mode:
            if user_input == "0":
                self.employee_selection_mode = False
                self.employee_matches = []
                self.current_step = "scheduled_host"
                # Prompt user to enter a new host name
                return "Please enter the name of the person you're scheduled to meet with:"
            selected_employee = await self.ai.handle_employee_selection(user_input, self.employee_matches)
            if selected_employee:
                # Store the selected host information
                self.visitor_info.host_confirmed = selected_employee["displayName"]
                self.visitor_info.host_email = selected_employee["email"]
                self.employee_selection_mode = False
                self.employee_matches = []
               
                # Fetch all meetings for the host for the day
                current_time = datetime.now(timezone.utc)
                meetings = await self.ai.get_scheduled_meetings(
                    self.visitor_info.host_email,
                    self.visitor_info.visitor_name,
                    current_time
                )
                print(f"[DEBUG] Selected host: {self.visitor_info.host_confirmed} ({self.visitor_info.host_email})")
                print(f"[DEBUG] get_scheduled_meetings returned: {meetings}")
               
                if not meetings:
                    self.current_step = "scheduled_confirm"
                    return "No meetings found for this host today. Would you like to check in as a guest instead?\n1. Yes, check in as guest\n2. No, re-enter host name\n\nType '1' or '2' to proceed."
               
                # Store the meetings list and enter selection mode
                self.scheduled_meeting_selection_mode = True
                self.scheduled_meeting_options = meetings
               
                # Show meetings for selection
                options = "Please select your meeting from the list below by number:\n"
                for i, meeting in enumerate(meetings, 1):
                    event = meeting['original_event']
                    start_time = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                    end_time = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                    pk_start = start_time + timedelta(hours=5)
                    pk_end = end_time + timedelta(hours=5)
                    options += f"{i}. {pk_start.strftime('%b %d, %I:%M %p')} - {pk_end.strftime('%I:%M %p')} | {meeting.get('purpose','No Purpose')}\n"
                options += "0. None of these / My meeting is not listed"
                return options
            else:
                options = "Please select a valid number:\n"
                for i, emp in enumerate(self.employee_matches, 1):
                    dept = emp.get("department", "Unknown Department")
                    options += f"  {i}. {emp['displayName']} ({dept})\n"
                options += "  0. None of these / Enter a different name"
                return options

        # Handle meeting selection mode
        if hasattr(self, 'scheduled_meeting_selection_mode') and self.scheduled_meeting_selection_mode:
            # Accept both number and meeting text as input
            selected_idx = None
            if user_input.isdigit():
                idx = int(user_input)
                if idx == 0:
                    self.scheduled_meeting_selection_mode = False
                    self.scheduled_meeting_options = []
                    self.current_step = "scheduled_confirm"
                    return "No meeting selected. Would you like to check in as a guest instead?\n1. Yes, check in as guest\n2. No, re-enter host name\n\nType '1' or '2' to proceed."
                elif 1 <= idx <= len(self.scheduled_meeting_options):
                    selected_idx = idx - 1
            else:
                # Try to match by meeting text
                for i, meeting in enumerate(self.scheduled_meeting_options):
                    event = meeting['original_event']
                    start_time = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                    end_time = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                    pk_start = start_time + timedelta(hours=5)
                    pk_end = end_time + timedelta(hours=5)
                    meeting_text = f"{pk_start.strftime('%b %d, %I:%M %p')} - {pk_end.strftime('%I:%M %p')} | {meeting.get('purpose','No Purpose')}"
                    if user_input.strip() == meeting_text.strip():
                        selected_idx = i
                        break
                # Also allow matching the 'None of these' text
                if user_input.strip().lower().startswith("none of these"):
                    self.scheduled_meeting_selection_mode = False
                    self.scheduled_meeting_options = []
                    self.current_step = "scheduled_confirm"
                    return "No meeting selected. Would you like to check in as a guest instead?\n1. Yes, check in as guest\n2. No, re-enter host name\n\nType '1' or '2' to proceed."

            if selected_idx is not None:
                if not self.scheduled_meeting_options or not (0 <= selected_idx < len(self.scheduled_meeting_options)):
                    # If invalid selection, re-show the options
                    options = "Please select your meeting from the list below by number:\n"
                    for i, meeting in enumerate(self.scheduled_meeting_options, 1):
                        event = meeting['original_event']
                        start_time = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                        end_time = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                        pk_start = start_time + timedelta(hours=5)
                        pk_end = end_time + timedelta(hours=5)
                        options += f"{i}. {pk_start.strftime('%b %d, %I:%M %p')} - {pk_end.strftime('%I:%M %p')} | {meeting.get('purpose','No Purpose')}\n"
                    options += "0. None of these / My meeting is not listed\n"
                    options += "\nInvalid selection. Please enter a valid number."
                    return options
               
                # Get the selected meeting directly from our stored list
                meeting = self.scheduled_meeting_options[selected_idx]
                print(f"[DEBUG] Selected meeting: {meeting}")
                print(f"[DEBUG] Selected host: {self.visitor_info.host_confirmed} ({self.visitor_info.host_email})")
               
                # Store the meeting and update state
                self.visitor_info.scheduled_meeting = meeting
                self.current_step = "scheduled_confirm"
               
                # Show confirmation
                event = meeting['original_event']
                start_time = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                pk_start = start_time + timedelta(hours=5)
                pk_end = end_time + timedelta(hours=5)
                host = self.visitor_info.host_confirmed or "(Unknown Host)"
                location = event.get('location', {}).get('displayName', 'DPL Office')
                meeting_info = (
                    f"\u2705 Confirmation:\n"
                    f"You are scheduled to meet {host}\n"
                    f"\U0001F551 Time: {pk_start.strftime('%b %d, %I:%M %p')} – {pk_end.strftime('%I:%M %p')}\n"
                    f"\U0001F4CD Location: {location}\n"
                    f"Purpose: {meeting.get('purpose','No Purpose')}\n\n"
                    f"Type 'confirm' to proceed or 'back' to re-enter the host name."
                )
                return meeting_info

            # If no valid selection, re-show the options
            options = "Please select your meeting from the list below by number:\n"
            for i, meeting in enumerate(self.scheduled_meeting_options, 1):
                event = meeting['original_event']
                start_time = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                pk_start = start_time + timedelta(hours=5)
                pk_end = end_time + timedelta(hours=5)
                options += f"{i}. {pk_start.strftime('%b %d, %I:%M %p')} - {pk_end.strftime('%I:%M %p')} | {meeting.get('purpose','No Purpose')}\n"
            options += "0. None of these / My meeting is not listed\n"
            options += "\nNo valid selection. Please enter a valid number or meeting description."
            return options

        # Handle confirmation after meeting selection
        if self.current_step == "scheduled_confirm":
            if user_input.strip().lower() == "confirm":
                # Clear meeting selection state only after confirmation
                self.scheduled_meeting_selection_mode = False
                self.scheduled_meeting_options = []
                self.current_step = "complete"
                # Insert into DB and notify host
                if self.visitor_info.scheduled_meeting:
                    meeting = self.visitor_info.scheduled_meeting
                    scheduled_time = None
                    start_time = meeting.get('original_event', {}).get('start', {}).get('dateTime')
                    if start_time:
                        scheduled_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    await insert_visitor_to_db(
                        visitor_type="prescheduled",
                        full_name=self.visitor_info.visitor_name,
                        cnic=self.visitor_info.visitor_cnic,
                        phone=self.visitor_info.visitor_phone,
                        host=self.visitor_info.host_confirmed,
                        purpose=meeting['purpose'],
                        is_group_visit=False,
                        email=self.visitor_info.visitor_email,
                        scheduled_time=scheduled_time
                    )
                    try:
                        access_token = self.ai.get_system_account_token()
                        host_user_id = await self.ai.get_user_id(self.visitor_info.host_email, access_token)
                        system_user_id = await self.ai.get_user_id(self.ai._system_account_email, access_token)
                        chat_id = await self.ai.create_or_get_chat(host_user_id, system_user_id, access_token)
                        message = f"""Your scheduled visitor has arrived:\nName: {self.visitor_info.visitor_name}\nPhone: {self.visitor_info.visitor_phone}\nEmail: {self.visitor_info.visitor_email}\nScheduled Time: {meeting['scheduled_time']}\nPurpose: {meeting['purpose']}"""
                        await self.ai.send_message_to_host(chat_id, access_token, message)
                        print(f"Teams notification sent to {self.visitor_info.host_confirmed}")
                    except Exception as e:
                        print(f"Error in Teams notification process: {e}")
                    return f"Welcome! Please take a seat. {self.visitor_info.host_confirmed} has been notified of your arrival."
                else:
                    # Handle guest flow confirmation
                    await insert_visitor_to_db(
                        visitor_type="guest",
                        full_name=self.visitor_info.visitor_name,
                        cnic=self.visitor_info.visitor_cnic,
                        phone=self.visitor_info.visitor_phone,
                        host=self.visitor_info.host_confirmed,
                        purpose=self.visitor_info.purpose,
                        email=self.visitor_info.visitor_email
                    )
                    try:
                        await self.ai.schedule_meeting(
                            self.visitor_info.host_email,
                            self.visitor_info.visitor_name,
                            self.visitor_info.visitor_phone,
                            self.visitor_info.purpose
                        )
                    except Exception as e:
                        print(f"Error scheduling meeting: {e}")
                    return "Registration successful. Rebel presence incoming — host’s been warned"
            elif user_input.strip().lower() == "back":
                self.current_step = "scheduled_host"
                return "Please enter the name of the person you're scheduled to meet with."
            elif user_input == "1":
                self.visitor_info.visitor_type = "guest"
                self.current_step = "purpose"
                return "What is the purpose of your visit?"
            elif user_input == "2":
                self.current_step = "scheduled_host"
                return "Please enter the name of the person you're scheduled to meet with."
            else:
                # If we have a meeting selected, show the confirmation again
                if self.visitor_info.scheduled_meeting:
                    meeting = self.visitor_info.scheduled_meeting
                    event = meeting['original_event']
                    start_time = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                    end_time = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                    pk_start = start_time + timedelta(hours=5)
                    pk_end = end_time + timedelta(hours=5)
                    host = self.visitor_info.host_confirmed or "(Unknown Host)"
                    location = event.get('location', {}).get('displayName', 'DPL Office')
                    meeting_info = (
                        f"\u2705 Confirmation:\n"
                        f"You are scheduled to meet {host}\n"
                        f"\U0001F551 Time: {pk_start.strftime('%b %d, %I:%M %p')} – {pk_end.strftime('%I:%M %p')}\n"
                        f"\U0001F4CD Location: {location}\n"
                        f"Purpose: {meeting.get('purpose','No Purpose')}\n\n"
                        f"Type 'confirm' to proceed or 'back' to re-enter the host name."
                    )
                    return meeting_info
                return "Type 'confirm' to proceed or 'back' to re-enter the host name."

        # Handle '0' as a reset even when not in selection mode
        if user_input.strip() == "0":
            self.employee_selection_mode = False
            self.employee_matches = []
            self.current_step = "scheduled_host"
            return "Please enter the name of the person you're scheduled to meet with:"

        # Not in selection mode - search for the host
        employee = await self.ai.search_employee(user_input)
        if isinstance(employee, dict):
            # For single match, show it to user for confirmation (like guest flow)
            self.employee_selection_mode = True
            self.employee_matches = [employee]
            options = "I found the following match. Please select by number:\n"
            dept = employee.get("department", "Unknown Department")
            options += f"  1. {employee['displayName']} ({dept})\n"
            options += "  0. None of these / Enter a different name"
            return options
        elif isinstance(employee, list):
            self.employee_selection_mode = True
            self.employee_matches = employee
            options = "I found multiple potential matches. Please select one:\n"
            for i, emp in enumerate(employee, 1):
                dept = emp.get("department", "Unknown Department")
                options += f"  {i}. {emp['displayName']} ({dept})\n"
            options += "  0. None of these / Enter a different name"
            return options
        else:
            return "No matches found. Please enter a different name."

    async def _run_guest_host_step(self, user_input):
        employee = await self.ai.search_employee(user_input.strip())
        if isinstance(employee, dict):
            self.employee_selection_mode = True
            self.employee_matches = [employee]
            dept = employee.get("department", "Unknown Department")
            return (
                "I found the following match. Please select by number:\n"
                f"  1. {employee['displayName']} ({dept})\n"
                "  0. None of these / Enter a different name"
            )
        elif isinstance(employee, list) and len(employee) > 0:
            self.employee_selection_mode = True
            self.employee_matches = employee
            options = "I found multiple potential matches. Please select one:\n"
            for i, emp in enumerate(employee, 1):
                dept = emp.get("department", "Unknown Department")
                options += f"  {i}. {emp['displayName']} ({dept})\n"
            options += "  0. None of these / Enter a different name"
            return options
        else:
            return "No matches found. Please enter a different name."

class MessageRequest(BaseModel):
    message: str
    current_step: Optional[str] = None
    visitor_info: Optional[dict] = None

class MessageResponse(BaseModel):
    response: str
    next_step: str
    visitor_info: dict

@app.post("/process-message/", response_model=MessageResponse)
async def process_message(request: Request, message_req: MessageRequest):
    """Handle visitor message processing with proper error handling and CORS."""
    try:
        global ai_receptionist
        receptionist = DPLReceptionist(ai=ai_receptionist)
       
        # Restore state from frontend if provided
        if message_req.current_step:
            receptionist.current_step = message_req.current_step
           
        if message_req.visitor_info:
            # First, extract host information if available
            host_confirmed = message_req.visitor_info.get('host_confirmed')
            host_email = message_req.visitor_info.get('host_email')
            host_requested = message_req.visitor_info.get('host_requested')
            
            print(f"[DEBUG] Received from frontend - host_confirmed: {host_confirmed}, host_email: {host_email}, host_requested: {host_requested}")
            
            # Restore all visitor info attributes
            for k, v in message_req.visitor_info.items():
                if hasattr(receptionist.visitor_info, k):
                    # Special handling for host information
                    if k == 'host_confirmed' and (v is not None or host_confirmed):
                        value = v or host_confirmed
                        print(f"[DEBUG] Restoring host_confirmed={value}")
                        setattr(receptionist.visitor_info, k, value)
                    elif k == 'host_email' and (v is not None or host_email):
                        value = v or host_email
                        print(f"[DEBUG] Restoring host_email={value}")
                        setattr(receptionist.visitor_info, k, value)
                    elif k == 'host_requested' and (v is not None or host_requested):
                        value = v or host_requested
                        print(f"[DEBUG] Restoring host_requested={value}")
                        setattr(receptionist.visitor_info, k, value)
                    else:
                        setattr(receptionist.visitor_info, k, v)
            # Restore employee selection mode and matches if needed
            if message_req.visitor_info.get('employee_selection_mode'):
                receptionist.employee_selection_mode = True
                receptionist.employee_matches = message_req.visitor_info.get('employee_matches', [])
            # Restore scheduled meeting selection state
            if message_req.visitor_info.get('scheduled_meeting_selection_mode'):
                receptionist.scheduled_meeting_selection_mode = True
                receptionist.scheduled_meeting_options = message_req.visitor_info.get('scheduled_meeting_options', [])
            print("[DEBUG] visitor_info after restore:", receptionist.visitor_info.to_dict())
        # Check for prescheduled flow
        if message_req.visitor_info and message_req.visitor_info.get('visitor_type') == 'prescheduled':
            flow = PreScheduledFlow(ai=ai_receptionist)
            # Restore state for PreScheduledFlow
            if message_req.current_step:
                flow.current_step = message_req.current_step
            if message_req.visitor_info:
                for k, v in message_req.visitor_info.items():
                    if k in flow.visitor_info:
                        flow.visitor_info[k] = v
                # Restore selection modes if needed
                if message_req.visitor_info.get('employee_selection_mode'):
                    flow.employee_selection_mode = True
                    flow.employee_matches = message_req.visitor_info.get('employee_matches', [])
                if message_req.visitor_info.get('scheduled_meeting_selection_mode'):
                    flow.scheduled_meeting_selection_mode = True
                    flow.scheduled_meeting_options = message_req.visitor_info.get('scheduled_meeting_options', [])
            response = await flow.process_input(message_req.message)
            visitor_info = flow.visitor_info.copy()
            # Add selection modes to visitor_info for frontend state
            visitor_info['employee_selection_mode'] = flow.employee_selection_mode
            visitor_info['employee_matches'] = flow.employee_matches
            visitor_info['scheduled_meeting_selection_mode'] = flow.scheduled_meeting_selection_mode
            visitor_info['scheduled_meeting_options'] = flow.scheduled_meeting_options
            return MessageResponse(
                response=response,
                next_step=flow.current_step,
                visitor_info=visitor_info
            )
       
        # Process the message
        response = await receptionist.process_input(message_req.message)

        # Get updated visitor info
        visitor_info = {}
        if hasattr(receptionist.visitor_info, 'to_dict'):
            visitor_info = receptionist.visitor_info.to_dict()
        else:
            visitor_info = {k: v for k, v in vars(receptionist.visitor_info).items()
                          if not k.startswith('_')}
       
        # Add state info
        visitor_info['employee_selection_mode'] = receptionist.employee_selection_mode
        visitor_info['employee_matches'] = receptionist.employee_matches
       
        # Handle complete state
        if receptionist.current_step == 'complete':
            visitor_info['registration_completed'] = True
           
        return MessageResponse(
            response=response,
            next_step=receptionist.current_step,
            visitor_info=visitor_info
        )

    except Exception as e:
        print(f"Error processing message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def root():
    return {"message": "Welcome! Go to /login to start Microsoft authentication."}

@app.get("/employees")
def list_employees():
    tokens = get_valid_tokens()
    access_token = tokens["access_token"]
    url = "https://graph.microsoft.com/v1.0/users?$select=displayName,mail,id"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        log(f"Failed to fetch users: {resp.status_code} {resp.text}")
        return {"error": f"Failed to fetch users: {resp.text}"}
    users = resp.json().get("value", [])
    return {"users": users}

@app.post("/start-chat")
async def start_chat(request: Request, user_id: str = Form(...)):
    """Start a new chat with a user using delegated permissions."""
    try:
        # Get access token from session
        access_token = request.session.get('access_token')
        if not access_token:
            raise HTTPException(status_code=401, detail="Not authenticated")
           
        # Check if token is expired
        expires_at = request.session.get('expires_at', 0)
        if time.time() >= expires_at:
            # Token expired, try to refresh
            refresh_token = request.session.get('refresh_token')
            if not refresh_token:
                raise HTTPException(status_code=401, detail="Session expired")
               
            # Refresh token
            token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
            data = {
                "client_id": CLIENT_ID,
                "scope": " ".join(auth_config['scope']),
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "client_secret": CLIENT_SECRET,
            }
            resp = requests.post(token_url, data=data)
            if resp.status_code != 200:
                raise HTTPException(status_code=401, detail="Token refresh failed")
               
            tokens = resp.json()
            access_token = tokens['access_token']
            request.session['access_token'] = access_token
            request.session['refresh_token'] = tokens.get('refresh_token', refresh_token)
            request.session['expires_at'] = time.time() + tokens.get('expires_in', 3600)
       
        # Get current user ID
        headers = {"Authorization": f"Bearer {access_token}"}
        me_resp = requests.get("https://graph.microsoft.com/v1.0/me", headers=headers)
        if me_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get current user info")
        current_user_id = me_resp.json()["id"]
       
        # Create chat
        chat_url = "https://graph.microsoft.com/v1.0/chats"
        chat_body = {
            "chatType": "oneOnOne",
            "members": [
                {
                    "@odata.type": "#microsoft.graph.aadUserConversationMember",
                    "roles": ["owner"],
                    "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{current_user_id}')"
                },
                {
                    "@odata.type": "#microsoft.graph.aadUserConversationMember",
                    "roles": ["owner"],
                    "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{user_id}')"
                }
            ]
        }
       
        chat_resp = requests.post(
            chat_url,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json=chat_body
        )
       
        if chat_resp.status_code not in (201, 200):
            raise HTTPException(status_code=400, detail=f"Failed to create chat: {chat_resp.text}")
           
        chat_id = chat_resp.json().get("id")
        return {"chat_id": chat_id}
       
    except HTTPException as e:
        raise e
    except Exception as e:
        log(f"Error in start-chat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/send-employee-message")
async def send_employee_message(request: Request, chat_id: str = Form(...), message: str = Form(...)):
    """Send a message in a Teams chat using delegated permissions."""
    try:
        # Get access token from session
        access_token = request.session.get('access_token')
        if not access_token:
            raise HTTPException(status_code=401, detail="Not authenticated")
           
        # Check if token is expired
        expires_at = request.session.get('expires_at', 0)
        if time.time() >= expires_at:
            # Token expired, try to refresh
            refresh_token = request.session.get('refresh_token')
            if not refresh_token:
                raise HTTPException(status_code=401, detail="Session expired")
               
            # Refresh token
            token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
            data = {
                "client_id": CLIENT_ID,
                "scope": " ".join(auth_config['scope']),
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "client_secret": CLIENT_SECRET,
            }
            resp = requests.post(token_url, data=data)
            if resp.status_code != 200:
                raise HTTPException(status_code=401, detail="Token refresh failed")
               
            tokens = resp.json()
            access_token = tokens['access_token']
            request.session['access_token'] = access_token
            request.session['refresh_token'] = tokens.get('refresh_token', refresh_token)
            request.session['expires_at'] = time.time() + tokens.get('expires_in', 3600)
       
        # Send message
        url = f"https://graph.microsoft.com/v1.0/chats/{chat_id}/messages"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        data = {"body": {"contentType": "text", "content": message}}
       
        resp = requests.post(url, headers=headers, json=data)
        if resp.status_code == 201:
            log("Message sent successfully")
            return {"status": "success", "message": "Message sent!"}
        else:
            log(f"Failed to send message: {resp.status_code} {resp.text}")
            raise HTTPException(status_code=400, detail=f"Failed to send message: {resp.text}")
           
    except HTTPException as e:
        raise e
    except Exception as e:
        log(f"Error in send-employee-message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="localhost", port=port)
