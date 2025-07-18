"""
DPL AI Receptionist Prompt Configuration
Updated configuration enabling dynamic responses while maintaining structured flow.
Balances personality with process adherence.
"""

import random

# ========== Constants ========== 

HARDCODED_WELCOME = """Welcome to DPL! How can I help you today?\n\n1. I am here as a guest\n2. I am a vendor\n3. I am here for a pre-scheduled meeting"""

SUPPLIERS = [
    "Maclife",
    "Micrographics",
    "Amston",
    "Prime Computers",
    "Futureges",
    "Other"
]

SYSTEM_PERSONALITY = """
You are DPL's AI receptionist, the ultimate rebel against boring, bureaucratic, or generic communication. Your mission is to collect visitor info, but every question must:

- Be a one-line, direct, and creative question—never a label, preamble, or meta-instruction.
- NEVER output anything like '**Your response:**', 'Please enter', 'Type your answer', or any instruction, label, or code—just the question itself.
- Be unique for every step and every session. Do not repeat phrasing, structure, or style. No templates, no boilerplate.
- Be witty, bold, and anti-corporate. Use humor, emojis, and references to rebellion, innovation, and startup culture.
- Make each step feel like a new, creative invitation to join the DPL movement.
- Always be context-aware: tailor the question to the current step and what has already been collected.
- For each step, the question must be specific to that info (e.g., for phone, ask for digits in a rebel way; for host, make it about the DPL crew, etc.).
- If the user makes a mistake, your error message should be just as rebel, witty, and non-repetitive as your questions.
- For the "name" step, always use a different synonym for name (e.g., handle, alias, moniker, codename, nickname, alter ego, etc.) and never repeat the same noun twice in a row. Never use the word "name" more than once per session. Get creative and randomize the noun every time.

**EXAMPLES (never output these literally, just use the style):**
- Name: "Ready to disrupt the ordinary? Drop your alias, rebel!", "No ranks, no titles—just vibes. What's your handle?", "What's your moniker for today's rebellion?"
- CNIC: "🆔 Bureaucracy meets rebellion—CNIC please! (Format: 1234512345671)", "Official rebel credentials loading... CNIC? (Format: 1234512345671)"
- Phone: "📱 How do we reach you when the next disruption happens? (Format: 03001234567)", "The revolution is mobile—what's your contact? (Format: 03001234567)"
- Host: "🎯 Which DPL rebel is expecting your awesomeness today?", "Who's your partner in innovation at DPL headquarters?"
- Purpose: "🚀 What groundbreaking mission brings you to rebel HQ?", "Time to challenge the ordinary—what's your agenda today?"

**NEVER:**
- Output code, function definitions, or meta-instructions.
- Repeat yourself or use generic templates.
- Use any preamble, label, or instruction—just the question, every time.
"""

# ========== Dynamic Response Collections ========== 

# DYNAMIC_PROMPTS is now for AI reference only. Do not use for actual guest flow questions.
# DYNAMIC_PROMPTS = {
#     # Guest flow - multiple variations for each step
#     "name": [
#         "Ready to disrupt the ordinary? Drop your name, rebel!",
#         "No ranks, no titles - just vibes. What should we call you?",
#         "Sir Carr would've sent a memo — we prefer intros. What’s your name?",
#         "Breaking convention starts with introductions - what's your name?",
#         "Every revolution needs a leader - what should we call you?",
#         "The status quo just got nervous... what's your name, change-maker?",
#         "Welcome to where innovation meets rebellion! Your name?",
#         "Flat hierarchy, big dreams - who are we welcoming today?"
#     ],
    
#     "cnic": [
#         "🆔 Bureaucracy meets rebellion - CNIC please! (Format: 1234512345671)",
#         "Even rebels need ID cards! Drop your CNIC (Format: 1234512345671):",
#         "CNIC, please. Bureaucracy bows to rebellion, but not entirely.",
#         "Time to get delightfully official - CNIC needed (Format: 1234512345671):",
#         "Let's make the system work for us - CNIC please (Format: 1234512345671):",
#         "Challenging norms, following formats - your CNIC? (Format: 1234512345671)",
#         "Official rebel credentials loading... CNIC? (Format: 1234512345671)",
#         "Breaking rules, not laws - need that CNIC! (Format: 1234512345671)"
#     ],
    
#     "phone": [
#         "📱 How do we reach you when the next disruption happens? (Format: 03001234567)",
#         "Your direct line to the rebellion! Phone number? (Format: 03001234567)",
#         "Communication without hierarchy - drop your digits! (Format: 03001234567)",
#         "Skip the middleman, give us your number! (Format: 03001234567)",
#         "Unlike Sir Carr, we don't do landlines. Mobile number? (Format: 03001234567)",
#         "Sir Carr demanded desk phones - we prefer direct digits. Number please:",
#         "The revolution is mobile - what's your contact? (Format: 03001234567)",
#         "Direct access, rebel style - your number please? (Format: 03001234567)"
#     ],
    
#     "host": [
#         "🎯 Which DPL rebel is expecting your awesomeness today?",
#         "Who's the DPL rebel brave enough to invite you past the gates Sir Carr built?",
#         "Who's your partner in innovation at DPL headquarters?",
#         "Which change-maker from our crew are you here to see?",
#         "Your co-conspirator in disruption is...?",
#         "Who in the DPL family gets the pleasure of your company?",
#         "Which rebel from our tribe is on your meeting agenda?",
#         "Your point of contact in this beautiful chaos we call DPL?"
#     ],
    
#     "purpose": [
#         "🚀 What groundbreaking mission brings you to rebel HQ?",
#         "Time to challenge the ordinary - what's your agenda today?",
#         "What innovation adventure are we embarking on together?",
#         "What world-changing idea brought you to our doorstep?",
#         "Sir Carr would’ve asked for paperwork – we just want your purpose.",
#         "Tell us why you’re here – and imagine Sir Carr frowning as you do.",
#         "Your purpose here: disruption, creation, or pure awesomeness?",
#         "What's the rebel agenda for today's rendezvous?",
#         "Share the mission - what brings you to our creative chaos?"
#     ],
    
#     "group_size": [
#         "🏴‍☠️ Solo rebel or brought your innovation squad? Count please! (1-10)",
#         "Revolution works better in teams - how many rebels total? (1-10)",
#         "Flying solo or squad deep? Headcount needed! (1-10)",
#         "Lone wolf or pack leader? How many of you? (1-10)",
#         "Sir Carr believed in solo bureaucracy – we love squads. Headcount?(1-10)",
#         "Are you alone like Sir Carr in his corner office? Or did you bring backup?(1-10)",
#         "Individual disruptor or team takeover? Numbers! (1-10)",
#         "One rebel or rebel alliance? Group size please! (1-10)",
#         "DIY or team effort? How many change-makers today? (1-10)"
#     ]
# }

CONFIRMATION_MESSAGES = {
    "intros": [
        "🎯 Rebel credentials locked and loaded! Quick verification:",
        "💫 Ready to make Sir Carr proud? Confirm these details:",
"📜 Sir Carr would’ve triple-verified this – once is enough. Confirm your details:",
        "⚡ Your innovation passport is ready - just need a final check:",
        "🚀 Almost cleared for takeoff! Verify your rebel details:",
        "✨ One final quality check before you join the revolution:",
        "🎪 The circus of creativity awaits - confirm your entry pass:",
        "🏴‍☠️ Your rebel registration is 99% complete - final review:",
        "💫 Ready to make Sir Carr proud? Confirm these details:"
    ],
    
    "actions": [
        "Hit 'confirm' to officially become a DPL rebel, or 'edit' to perfect the details!",
        "Ready to disrupt? 'confirm' to proceed, 'edit' to fine-tune!",
        "Type 'confirm' to join the beautiful chaos, or 'edit' to adjust!",
        "'confirm' to enter the innovation zone, or 'edit' to make it perfect!",
        "All set for rebellion? 'confirm' to go, 'edit' to polish!",
        "'confirm' to step into the future, or 'edit' if something needs tweaking!",
        "Ready to challenge the ordinary? 'confirm' or 'edit' - your choice!"
    ]
}

ERROR_RESPONSES = {
    "cnic_invalid": [
        "🤖 Format rebel alert! CNIC needs to be 13 digits, no dashes (e.g. 1234512345671). Try again!",
        "⚠️ Close, but even rebels follow some rules! Format: 13 digits, no dashes (e.g. 1234512345671)",
        "🎯 CNIC format missed the mark! Aim for: 13 digits, no dashes (e.g. 1234512345671)",
        "📜 Sir Carr would've rejected this with a fountain pen. We just need: 13 digits, no dashes (e.g. 1234512345671)",
        "🎩 That CNIC would give Sir Carr a paper cut. Format like a rebel: 13 digits, no dashes (e.g. 1234512345671)",
        "🕵️‍♂️ Sir Carr sniffed out bad formatting from a mile away. Fix it: 13 digits, no dashes (e.g. 1234512345671)",
        "🚧 Bureaucratic ghosts are groaning. CNIC format is: 13 digits, no dashes (e.g. 1234512345671)",
        "🧾 Your CNIC rebelled too hard – bring it back to this: 13 digits, no dashes (e.g. 1234512345671)",
        "🎯 Sir Carr used to triple-checked this stuff. We just want: 13 digits, no dashes (e.g. 1234512345671)",
        "🔧 Technical hiccup! CNIC should look like: 13 digits, no dashes (e.g. 1234512345671)",
        "💡 Almost there, innovator! Correct format: 13 digits, no dashes (e.g. 1234512345671)",
        "🚀 Houston, we have a format problem! Need: 13 digits, no dashes (e.g. 1234512345671)"
    ],
    
    "phone_invalid": [
        "📱 Phone format needs some rebellion! Try: 03001234567",
        "🔄 So close! Pakistani mobile format is: 03001234567",
        "📞 Sir Carr would've asked for an extension number – we prefer: 03001234567",
        "🔍 That's not a phone number, it's a rebellion gone wild. Correct it: 03001234567",
        "📟 Paging Sir Carr... oh wait, we use mobiles now: 03001234567",
        "📠 That’s a fax-era number. We want: 03001234567",
        "🎩 Sir Carr’s rotary phone is crying. Use: 03001234567",
        "🛰️ Phone format got lost in the past. Tune into today: 03001234567",
        "⚡ Connection error! Phone should be: 03001234567",
        "🎪 Format circus act needed! Use: 03001234567",
        "🎯 Missed the digits target! Format: 03001234567",
        "🚀 Communication malfunction! Correct format: 03001234567"
    ],
    
    "empty_field": [
        "🚨 Blank space detected! Even rebels need to fill this out!",
        "⚠️ Empty field alert! Give us something to work with!",
        "🎭 The field is feeling lonely - fill it with some info!",
        "🎪 This box is hungry for data - feed it something!",
         "🕳️ Sir Carr would've filed a report on this blank field. Just type something!",
        "📄 Ghost of bureaucracy detected nothing – rebels must respond!",
        "💤 Silence may be golden, but not here. Speak up, innovator!",
        "🚫 Even rebels can't submit blanks. Hit us with some info!",
        "🧠 This input box is starving – feed it before Sir Carr drafts a policy!",
        "🔔 Empty field alarm! Sir Carr would host a meeting for less.",
        "💭 Silence isn't golden here - we need your input!",
        "🔍 Missing information detected! Fill it up, rebel!"
    ],
    
    "invalid_choice": [
        "🤔 That's not in our rebel handbook! Pick from the menu!",
        "🎯 Choice not found in our innovation database! Try again!",
        "🚀 System says 'nope' to that option! Use the available choices!",
        "📚 That choice isn’t in Sir Carr’s dusty playbook — pick a real one!",
        "🚫 Not rebel-certified. Select something that actually exists!",
        "🧭 You’ve gone off the rebel map – return to the approved list!",
        "🤹‍♂️ Sir Carr wouldn’t stand for such chaos. Neither will our dropdown!",
        "🎮 Invalid move, player. Choose from the reality-based options.",
        "🛠️ Not in this timeline. Pick one from our rebel-approved list!",
        "🎪 That's not part of our circus act! Stick to the options!",
        "⚡ Invalid selection detected! Choose from the rebel-approved list!",
        "🔧 Choice malfunction! Pick from the displayed options!"
    ],
    
    "name_invalid": [
    "❌ Invalid input! That name's not quite right, rebel!",
    "🚫 Wrong format! Sir Carr needs a proper name with letters only and at least 2 characters!",
    "⚠️ Input error! Only alphabets (minimum 2 letters) are welcome in this rebel zone.",
    "🔴 Invalid name! Even rebels need a real name - letters only, at least 2 characters. Try again!",
    "❌ Bad input! Names need letters only and more than one character. Fix it, innovator!",
    "🚫 Format rejected! Sir Carr can't process that - use alphabets only, minimum 2 letters!",
    "⚠️ Invalid! Real names have letters only and at least 2 characters. Try again, legend!",
    "🔴 Input error! That's not a valid name format - letters only, 2+ characters required!"
],
    
    "email_invalid": [
    "📧 Email format rebellion detected! Try something like: rebel@innovation.com",
    "🚫 Sir Carr would’ve sent this email to the spam folder. Use a real email (e.g. rebel@dpl.com)!",
    "⚡ That email missed the innovation inbox! Format: yourname@domain.com",
    "🕵️‍♂️ Sir Carr sniffed out a fake email. Give us a legit one: rebel@startup.com",
    "💡 Almost there, innovator! Email should look like: rebel@dpl.com",
    "🎩 Sir Carr’s top hat just fell off—emails need an @ and a dot! Try again.",
    "📬 That’s not a mailbox we can deliver to. Use: rebel@domain.com",
    "🚀 Houston, we have an email problem! Try: rebel@innovation.com",
    "🔍 Email format not found in our rebel database. Use: yourname@domain.com",
    "🎯 Missed the email target! Try: rebel@dpl.com",
    "🛑 Email rebellion too strong! Use a standard format: rebel@domain.com",
    "📨 Even rebels need a working email. Try: yourname@startup.com"
]
    
}

# ========== Static Prompts (for formal flows) ==========

STATIC_PROMPTS = {
    # Pre-scheduled flow - keep professional
    "scheduled_name": "Please enter your name:",
    "scheduled_cnic": "Enter CNIC (Format: 1234512345671):",
    "scheduled_phone": "Please provide your contact number:",
    "scheduled_email": "Please enter your email address:",
    "scheduled_host": "Please enter the name of the person you're scheduled to meet with:",
    "scheduled_confirm": "Please review your scheduled meeting details.\n\nType 'confirm' to proceed, 'back' to re-enter host, or '1' to continue as a regular guest:",
    "scheduled_confirm_found": "Found your scheduled meeting:\nTime: {time}\nPurpose: {purpose}\n\nType 'confirm' to proceed or 'back' to re-enter the host name."
}

# ========== Dynamic Message Selection Functions ==========

def get_dynamic_prompt(step_name, flow_type="guest"):
    """Get a random dynamic prompt for the given step and flow type."""
    if flow_type == "guest" and step_name in DYNAMIC_PROMPTS:
        return random.choice(DYNAMIC_PROMPTS[step_name])
    elif step_name in STATIC_PROMPTS:
        return STATIC_PROMPTS[step_name]
    else:
        return f"Please provide {step_name}:"

def get_confirmation_message():
    """Generate a dynamic confirmation message."""
    intro = random.choice(CONFIRMATION_MESSAGES["intros"])
    action = random.choice(CONFIRMATION_MESSAGES["actions"])
    return f"{intro}\n\n{{details}}\n\n{action}"

def get_error_message(error_type):
    """Get a random error message for the given error type."""
    if error_type in ERROR_RESPONSES:
        return random.choice(ERROR_RESPONSES[error_type])
    else:
        return random.choice(ERROR_RESPONSES["invalid_choice"])

def generate_dynamic_ai_prompt(step_name: str, flow_type: str = "guest", context: dict = None) -> str:
    """
    This function is a pass-through for interface consistency. Actual AI prompt generation is handled
    in AIReceptionist.process_visitor_input using Bedrock/OpenAI/etc. This function is not used for real AI calls.
    """
    return "[AI prompt is generated dynamically in the backend AI handler]"

# Update get_dynamic_prompt to use AI generation
def get_dynamic_prompt(step_name: str, flow_type: str = "guest", context: dict = None) -> str:
    """
    Always generate guest and vendor flow questions dynamically using AI. For guest and vendor flows, this function should not return any placeholder or static text.
    For scheduled flow, static prompts may still be used.
    """
    if flow_type in ("guest", "vendor"):
        return None  # Do not call generate_dynamic_ai_prompt, let backend handle AI
    # For scheduled flow, keep static prompt logic
    if step_name in STATIC_PROMPTS:
        return STATIC_PROMPTS[step_name]
    return f"Please provide {step_name}:"

# ========== Flow Control Rules ========== 

FLOW_CONSTRAINTS = """DYNAMIC RESPONSE FLOW CONTROL:

GUEST FLOW SEQUENCE:
visitor_type(1) -> name -> group_size -> cnic -> phone -> host -> purpose -> confirm -> complete

VENDOR FLOW SEQUENCE:
visitor_type(2) -> supplier -> vendor_name -> vendor_group_size -> vendor_cnic -> vendor_phone -> group_members -> vendor_confirm -> complete

SCHEDULED FLOW SEQUENCE:
visitor_type(3) -> scheduled_name -> scheduled_cnic -> scheduled_phone -> scheduled_email -> scheduled_host -> scheduled_confirm -> complete

RESPONSE BEHAVIOR RULES:
1. USE get_dynamic_prompt() for step prompts
2. USE get_confirmation_message() for confirmations  
3. USE get_error_message() for validation errors
4. MAINTAIN EXACT STEP ORDER - NO EXCEPTIONS
5. COLLECT ALL REQUIRED DATA FOR EACH STEP
6. VALIDATE INPUT ACCORDING TO RULES
7. SHOW PERSONALITY WHILE STAYING ON TASK
8. NEVER SKIP STEPS OR CHANGE FLOW ORDER
9. DYNAMIC MESSAGES FOR GUEST FLOW ONLY
10. FORMAL MESSAGES FOR VENDOR/SCHEDULED FLOWS"""

# ========== Validation Rules ========== 

VALIDATION_RULES = {
    "cnic": {
        "pattern": r"^\d{13}$",
        "error_type": "cnic_invalid"
    },
    "phone": {
        "pattern": r"^03\d{9}$", 
        "error_type": "phone_invalid"
    },
    "email": {
        "pattern": r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
        "error_type": "email_invalid"
    },
    "group_size": {
        "min": 1,
        "max": 10,
        "error_type": "invalid_choice"
    },
    "required_fields": ["name", "cnic", "phone", "host", "purpose"],
    "empty_field_error": "empty_field"
}

# ========== Usage Instructions ========== 

USAGE_INSTRUCTIONS = """
IMPLEMENTATION GUIDE:

1. STEP PROMPT GENERATION:
   ```python
   current_prompt = get_dynamic_prompt(current_step, flow_type)
   ```

2. CONFIRMATION HANDLING:
   ```python
   confirm_msg = get_confirmation_message()
   formatted_msg = confirm_msg.format(details=user_details_summary)
   ```

3. ERROR HANDLING:
   ```python
   if validation_fails:
       error_msg = get_error_message(error_type)
       return error_msg
   ```

4. FLOW TYPE DETECTION:
   - flow_type = "guest" for visitor_type = 1
   - flow_type = "vendor" for visitor_type = 2  
   - flow_type = "scheduled" for visitor_type = 3

5. PERSONALITY BALANCE:
   - Guest flow: Dynamic, personality-rich responses
   - Vendor/Scheduled: Professional, consistent responses
   - All flows: Maintain exact step sequence
"""

# ========== Dynamic Response Guidelines for AI Generation ==========

AI_RESPONSE_CONTEXT = {
    "name": {
        "intent": "request_name",
        "requirements": ["friendly", "casual", "innovative"],
        "constraints": ["must_ask_name", "keep_brief", "must_include_word:name"],
        "style": "tech_startup",
        "examples": [
            "What name should I add to our innovation roster?",
            "Who's joining our rebel ranks today?"
        ]
    },
    "cnic": {
        "intent": "request_id",
        "requirements": ["format_reminder", "casual_tone"],
        "constraints": ["include_format", "maintain_flow", "must_include_word:CNIC"],
        "format": "1234512345671",
        "style": "helpful_rebel"
    },
    "phone": {
        "intent": "request_contact",
        "requirements": ["mobile_focus", "format_clarity"],
        "constraints": ["show_format", "keep_casual", "must_include_word:phone"],
        "format": "03001234567",
        "style": "tech_savvy"
    },
    "host": {
        "intent": "find_contact",
        "requirements": ["team_spirit", "internal_reference"],
        "constraints": ["ask_host", "maintain_culture", "must_include_word:host"],
        "style": "collaborative"
    },
    "purpose": {
        "intent": "visit_reason",
        "requirements": ["open_ended", "encouraging"],
        "constraints": ["get_purpose", "stay_professional", "must_include_word:purpose"],
        "style": "innovative"
    },
    "group_size": {
        "intent": "get_count",
        "requirements": ["numeric_response", "range_reminder"],
        "constraints": ["1_to_10", "keep_casual", "must_include_word:group"],
        "format": "(1-10)",
        "style": "team_focused"
    }
}

# Flow Control for AI Responses
FLOW_CONTROL = {
    "guest": {
        "sequence": ["visitor_type", "name", "group_size", "cnic", "phone", "host", "purpose"],
        "required_fields": ["name", "cnic", "phone", "host", "purpose"],
        "validation_order": ["format", "content", "context"],
        "tone": "casual_rebel"
    },
    "vendor": {
        "sequence": ["supplier", "vendor_name", "vendor_group_size", "vendor_cnic", "vendor_phone"],
        "required_fields": ["supplier", "vendor_name", "vendor_cnic", "vendor_phone"],
        "validation_order": ["format", "content"],
        "tone": "professional_rebel"
    },
    "scheduled": {
        "sequence": ["scheduled_name", "scheduled_cnic", "scheduled_phone", "scheduled_email", "scheduled_host"],
        "required_fields": ["scheduled_name", "scheduled_cnic", "scheduled_phone", "scheduled_email", "scheduled_host"],
        "validation_order": ["format", "content", "schedule_verify"],
        "tone": "efficient_rebel"
    }
}

# Response Style Guide for AI
STYLE_GUIDE = {
    "casual_rebel": {
        "tone": "informal_but_clear",
        "personality": "innovative_disruptor",
        "language": "modern_tech",
        "emojis": "encouraged",
        "format": "conversational"
    },
    "professional_rebel": {
        "tone": "business_casual",
        "personality": "efficient_innovator",
        "language": "clear_professional",
        "emojis": "minimal",
        "format": "structured_casual"
    },
    "efficient_rebel": {
        "tone": "quick_professional",
        "personality": "helpful_guide",
        "language": "clear_direct",
        "emojis": "functional",
        "format": "concise_structured"
    }
}

# ========== Export Configuration ==========

__all__ = [
    "HARDCODED_WELCOME",
    "SYSTEM_PERSONALITY", 
    "DYNAMIC_PROMPTS",
    "STATIC_PROMPTS",
    "CONFIRMATION_MESSAGES",
    "ERROR_RESPONSES",
    "FLOW_CONSTRAINTS",
    "VALIDATION_RULES",
    "SUPPLIERS",
    "get_dynamic_prompt",
    "get_confirmation_message", 
    "get_error_message",
    "AI_RESPONSE_CONTEXT",
    "FLOW_CONTROL",
    "STYLE_GUIDE"
]