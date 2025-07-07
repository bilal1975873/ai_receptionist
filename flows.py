# Guest flow requirements, steps, and validation logic
import re
import random
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

# Validation patterns with strict rules
NAME_PATTERN = r"^[A-Za-z\s]{2,50}$"  # Only letters and spaces, 2-50 chars
CNIC_PATTERN = r"^\d{13}$"  # Format: 13 digits, no dashes
PHONE_PATTERN = r"^03\d{9}$"  # Format: 03001234567
EMAIL_PATTERN = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

# Hardcoded validation error messages
ERROR_MESSAGES = {
    "name": "Oops! Keep it simple - just letters and spaces for your name (2-50 characters)",
    "cnic": "Hold up! That CNIC format isn't quite right. It should be 13 digits, no dashes (e.g. 1234512345671)",
    "phone": "Almost there! Just need your phone number like this: 03001234567",
    "email": "That email looks a bit off. Mind giving it another shot?",
    "group_size": "Group size must be a number between 1 and 10",
    "empty": "This field cannot be empty",
    "supplier": "Please select a valid supplier from the list.",
    "vendor_name": "Please enter a valid name for the vendor."
}

# Dynamic validation messages with multiple variations
DYNAMIC_ERROR_MESSAGES = {
    "name": [
        "Oops! Keep it simple - just letters and spaces for your name (2-50 characters)",
        "Hey REBEL! Names should be letters only, 2-50 characters long",
        "Let's stick to letters for your name - nothing fancy needed!"
    ],
    "cnic": [
        "Hold up! That CNIC format isn't quite right. It should be 13 digits, no dashes (e.g. 1234512345671)",
        "CNIC needs to be 13 digits, no dashes. Give it another shot!",
        "Quick fix needed: Make sure your CNIC is 13 digits, no dashes (e.g. 1234512345671)"
    ],
    "phone": [
        "Almost there! Just need your phone number like this: 03001234567",
        "Phone number should start with '03' and be 11 digits total",
        "Quick checkpoint: Phone format is 03001234567 - no spaces or dashes needed"
    ],
    "email": [
        "That email looks a bit off. Mind giving it another shot?",
        "Hmm, double-check that email format for me?",
        "Let's make sure we've got a valid email here"
    ]
}

def validate_name(name: str) -> bool:
    """Validate name: only letters and spaces allowed"""
    if not name or len(name.strip()) < 2:
        return False
    return bool(re.match(NAME_PATTERN, name))

def validate_cnic(cnic: str) -> bool:
    """Validate CNIC format: 13 digits, no dashes"""
    return bool(re.match(CNIC_PATTERN, cnic))

def validate_phone(phone: str) -> bool:
    """Validate phone number format"""
    return bool(re.match(PHONE_PATTERN, phone))

def validate_email(email: str) -> bool:
    """Validate email format"""
    return bool(re.match(EMAIL_PATTERN, email))

def validate_group_size(size: str) -> bool:
    """Validate group size (1-10)"""
    try:
        size_int = int(size)
        return 1 <= size_int <= 10
    except ValueError:
        return False

SUPPLIERS = [
    "Maclife",
    "Micrographics",
    "Amston",
    "Prime Computers",
    "Futureges",
    "Other"
]

# Scheduled flow requirements and steps
scheduled_flow = {
    "required_fields": ["visitor_name", "visitor_phone", "visitor_email", "host_confirmed"],
    "steps": ["scheduled_name", "scheduled_phone", "scheduled_email", "scheduled_host", "scheduled_confirm", "complete"],
    "validations": {
        "visitor_phone": validate_phone,
        "visitor_email": validate_email
    }
}

# Guest flow requirements and steps
guest_flow = {    "required_fields": ["visitor_name", "visitor_cnic", "visitor_phone", "host_confirmed", "purpose"],
    "steps": ["name", "cnic", "phone", "host", "purpose", "confirm", "complete"],
    "validations": {
        "visitor_cnic": validate_cnic,
        "visitor_phone": validate_phone
    }
}

# Vendor flow requirements and steps
vendor_flow = {
    "required_fields": ["supplier", "visitor_name", "visitor_cnic", "visitor_phone"],
    "steps": ["supplier", "vendor_name", "vendor_group_size", "vendor_cnic", "vendor_phone", "vendor_confirm", "complete"],
    "validations": {
        "supplier": lambda x: x in SUPPLIERS or x == "Other",
        "visitor_cnic": validate_cnic,
        "visitor_phone": validate_phone,
        "vendor_name": validate_name,
        "group_size": validate_group_size
    }
}

class ResponseContext:
    def __init__(self):
        self.interaction_count = 0
        self.error_counts = {}
        self.last_field = None
        
    def increment_error(self, field: str):
        self.error_counts[field] = self.error_counts.get(field, 0) + 1
        
    def get_error_count(self, field: str) -> int:
        return self.error_counts.get(field, 0)

def validate_with_context(field: str, value: str, context: ResponseContext) -> Tuple[bool, str]:
    """Validate input with context-aware error messages"""
    validation_funcs = {
        "name": validate_name,
        "cnic": validate_cnic,
        "phone": validate_phone,
        "email": validate_email
    }
    
    validator = validation_funcs.get(field)
    if not validator:
        return True, ""
        
    is_valid = validator(value)
    if not is_valid:
        context.increment_error(field)
        error_messages = DYNAMIC_ERROR_MESSAGES.get(field, [ERROR_MESSAGES.get(field)])
        if isinstance(error_messages, list):
            error_count = context.get_error_count(field)
            index = min(error_count - 1, len(error_messages) - 1)
            error_msg = error_messages[index]
            
            # Add extra help after multiple errors
            if error_count > 2:
                hints = {
                    "name": "Just use regular letters, like 'John Smith'",
                    "cnic": "The dashes are important: 12345-1234567-1",
                    "phone": "Start with '03' followed by 9 more digits",
                    "email": "Make sure it includes @ and a valid domain"
                }
                error_msg = f"{error_msg}\n\nNeed help? {hints.get(field, '')}"
        else:
            error_msg = error_messages
            
        return False, error_msg
        
    return True, ""