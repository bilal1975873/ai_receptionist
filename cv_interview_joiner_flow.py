import re
import logging
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
from enum import Enum
from flows import validate_name, validate_cnic, validate_phone, validate_with_context, ResponseContext
from prompts import get_error_message, get_dynamic_prompt, get_confirmation_message
import asyncio
 # removed pymongo (no longer needed)
from datetime import timezone, timedelta

# Configure logging
logger = logging.getLogger(__name__)

class VisitorPurpose(Enum):
    """Enum for visitor purposes to ensure type safety"""
    CV_DROP = "CV Drop"
    INTERVIEW = "Interview"
    NEW_JOINER = "New Joiner"

class FlowStep(Enum):
    """Enum for flow steps to ensure type safety"""
    SELECT_OPTION = "select_option"
    NAME = "name"
    CNIC = "cnic"
    PHONE = "phone"
    CONFIRM = "confirm"
    COMPLETE = "complete"

class CVInterviewJoinerFlow:
    """
    Enhanced flow handler for CV Drop, Interview, and New Joiner visitor registration with dynamic personas.
    
    Features:
    - Type-safe enums for steps and purposes
    - Dynamic AI personas based on visitor purpose
    - Professional yet friendly tone for HR interactions
    - Purpose-specific interactions
    - Comprehensive error handling and logging
    - Input sanitization and validation
    - Retry mechanism for failed operations
    - Better state management
    """
    
    # Class constants
    MAX_RETRY_ATTEMPTS = 3
    VALID_CONFIRMATIONS = {"yes", "y", "confirm", "ok", "proceed"}
    HOST_NAME = "HR / Recruitment Team"
    
    def __init__(self, ai, visitor_info: Optional[Dict[str, Any]] = None):
        self.ai = ai
        self.visitor_info = visitor_info or {}
        self.response_context = ResponseContext()
        
        # Initialize current step
        current_step_str = self.visitor_info.get("current_step")
        self.current_step = self._get_step_enum(current_step_str) or FlowStep.SELECT_OPTION
        self.visitor_info["current_step"] = self.current_step.value
        
        # Initialize selected option
        purpose_str = self.visitor_info.get("purpose")
        self.selected_option = self._get_purpose_enum(purpose_str)
        
        logger.info(f"Flow initialized with step: {self.current_step}, purpose: {self.selected_option}")

    def _get_step_enum(self, step_str: Optional[str]) -> Optional[FlowStep]:
        """Safely convert string to FlowStep enum"""
        if not step_str:
            return None
        try:
            return FlowStep(step_str)
        except ValueError:
            logger.warning(f"Invalid step string: {step_str}")
            return None

    def _get_purpose_enum(self, purpose_str: Optional[str]) -> Optional[VisitorPurpose]:
        """Safely convert string to VisitorPurpose enum"""
        if not purpose_str:
            return None
        try:
            return VisitorPurpose(purpose_str)
        except ValueError:
            logger.warning(f"Invalid purpose string: {purpose_str}")
            return None

    def _get_persona_context(self) -> Dict[str, Any]:
        """Generate persona context based on visitor purpose"""
        if not self.selected_option:
            return {}
            
        # Base persona traits for all HR-related visitors
        base_persona = {
            "tone": "professional yet friendly, encouraging, supportive",
            "style": "warm but business-appropriate, confidence-building",
            "approach": "treat the person with respect and professionalism",
            "humor_level": "light and appropriate for professional setting",
            "respect_level": "high - acknowledge their career journey"
        }
        
        # Purpose-specific persona traits
        purpose_personas = {
            VisitorPurpose.CV_DROP: {
                **base_persona,
                "visitor_identity": "job seeker",
                "purpose_context": "dropping off CV for potential opportunities",
                "tone_adjustment": "encouraging, supportive of their job search",
                "greeting_style": "someone taking a positive step in their career",
                "professional_respect": "acknowledge their initiative in seeking opportunities"
            },
            VisitorPurpose.INTERVIEW: {
                **base_persona,
                "visitor_identity": "interview candidate", 
                "purpose_context": "attending an interview for a position",
                "tone_adjustment": "calming, confidence-building, professional",
                "greeting_style": "someone who's already impressed us enough to interview",
                "professional_respect": "acknowledge their qualifications and potential"
            },
            VisitorPurpose.NEW_JOINER: {
                **base_persona,
                "visitor_identity": "new team member",
                "purpose_context": "joining the organization as a new employee",
                "tone_adjustment": "welcoming, excited, team-oriented",
                "greeting_style": "new colleague and valued team member",
                "professional_respect": "acknowledge their skills and welcome them to the family"
            }
        }
        
        return purpose_personas.get(self.selected_option, base_persona)

    def _create_dynamic_prompt_context(self, step: str) -> Dict[str, Any]:
        """Create comprehensive context for AI prompt generation"""
        persona_context = self._get_persona_context()
        
        # Step-specific instructions
        step_contexts = {
            "name": {
                "request_type": "full name",
                "validation_hint": "your complete name for our records",
                "context_note": "for registration and identification purposes"
            },
            "cnic": {
                "request_type": "CNIC number", 
                "validation_hint": "national ID format (like 12345-1234567-1)",
                "context_note": "required for our security and documentation process"
            },
            "phone": {
                "request_type": "phone number",
                "validation_hint": "working contact number", 
                "context_note": "so our HR team can reach you if needed"
            }
        }
        
        return {
            "visitor_type": "hr_related_visitor",
            "current_step": step,
            "persona": persona_context,
            "step_context": step_contexts.get(step, {}),
            "purpose": self.selected_option.value if self.selected_option else "",
            "flow_stage": f"collecting {step} information",
            "communication_goal": "make the visitor feel welcomed and confident while getting necessary info"
        }

    def _sanitize_input(self, user_input: str) -> str:
        """Sanitize user input by trimming whitespace and removing dangerous characters"""
        if not isinstance(user_input, str):
            return ""
        
        # Basic sanitization
        sanitized = user_input.strip()
        # Remove potential script tags or HTML (basic protection)
        sanitized = re.sub(r'<[^>]*>', '', sanitized)
        return sanitized

    async def start_flow(self) -> str:
        """Initialize the flow and return the first prompt"""
        try:
            self.current_step = FlowStep.SELECT_OPTION
            self.visitor_info["current_step"] = self.current_step.value
            logger.info("Flow started")
            
            options = [purpose.value for purpose in VisitorPurpose]
            return f"Welcome! Please select your purpose:\n{', '.join(options)}"
            
        except Exception as e:
            logger.error(f"Error starting flow: {e}")
            return "Sorry, there was an error starting the registration. Please try again."

    async def process_input(self, user_input: str) -> str:
        """
        Process user input based on current step with comprehensive error handling
        """
        try:
            # Sanitize input
            clean_input = self._sanitize_input(user_input)
            
            # Sync state
            self._sync_state()
            
            logger.info(f"Processing input at step {self.current_step}: {clean_input[:50]}...")
            
            # Route to appropriate handler
            handler_map = {
                FlowStep.SELECT_OPTION: self._handle_option_selection,
                FlowStep.NAME: self._handle_name_input,
                FlowStep.CNIC: self._handle_cnic_input,
                FlowStep.PHONE: self._handle_phone_input,
                FlowStep.CONFIRM: self._handle_confirmation,
            }
            
            handler = handler_map.get(self.current_step)
            if not handler:
                logger.error(f"No handler found for step: {self.current_step}")
                return "An error occurred. Please restart the process."
            
            return await handler(clean_input)
            
        except Exception as e:
            logger.error(f"Error processing input: {e}")
            return "Sorry, there was an error processing your input. Please try again."

    def _sync_state(self):
        """Synchronize current step and selected option with visitor_info"""
        current_step_str = self.visitor_info.get("current_step")
        if current_step_str:
            step_enum = self._get_step_enum(current_step_str)
            if step_enum:
                self.current_step = step_enum
        
        purpose_str = self.visitor_info.get("purpose")
        if purpose_str:
            purpose_enum = self._get_purpose_enum(purpose_str)
            if purpose_enum:
                self.selected_option = purpose_enum

    async def _handle_option_selection(self, user_input: str) -> str:
        """Handle visitor purpose selection"""
        try:
            # Try to match input with valid purposes
            input_lower = user_input.lower()
            
            for purpose in VisitorPurpose:
                if purpose.value.lower() == input_lower:
                    self.selected_option = purpose
                    self.visitor_info["purpose"] = purpose.value
                    return await self._advance_to_step(FlowStep.NAME)
            
            # If no exact match, provide helpful error
            valid_options = [purpose.value for purpose in VisitorPurpose]
            return f"Invalid option. Please select one of: {', '.join(valid_options)}"
            
        except Exception as e:
            logger.error(f"Error handling option selection: {e}")
            return "Error processing your selection. Please try again."

    async def _handle_name_input(self, user_input: str) -> str:
        """Handle name input validation with persona"""
        try:
            if not user_input:
                # Generate persona-based error message
                error_context = self._create_dynamic_prompt_context("name")
                error_context["error_type"] = "empty_input"
                error_prompt = await self._get_ai_error_response(error_context)
                return error_prompt or get_error_message("empty")
            
            if not validate_name(user_input):
                # Generate persona-based error message for invalid name
                error_context = self._create_dynamic_prompt_context("name")
                error_context["error_type"] = "invalid_format"
                error_context["user_input"] = user_input
                error_prompt = await self._get_ai_error_response(error_context)
                return error_prompt or get_error_message("name_invalid")
            
            self.visitor_info["visitor_name"] = user_input
            return await self._advance_to_step(FlowStep.CNIC)
            
        except Exception as e:
            logger.error(f"Error handling name input: {e}")
            return "Error processing your name. Please try again."

    async def _handle_cnic_input(self, user_input: str) -> str:
        """Handle CNIC input validation with persona"""
        try:
            is_valid, error_msg = validate_with_context("cnic", user_input, self.response_context)
            if not is_valid:
                # Generate persona-based error message for invalid CNIC
                error_context = self._create_dynamic_prompt_context("cnic")
                error_context["error_type"] = "invalid_format"
                error_context["user_input"] = user_input
                error_prompt = await self._get_ai_error_response(error_context)
                return error_prompt or get_error_message("cnic_invalid")
            
            self.visitor_info["visitor_cnic"] = user_input
            return await self._advance_to_step(FlowStep.PHONE)
            
        except Exception as e:
            logger.error(f"Error handling CNIC input: {e}")
            return "Error processing your CNIC. Please try again."

    async def _handle_phone_input(self, user_input: str) -> str:
        """Handle phone input validation with persona"""
        try:
            is_valid, error_msg = validate_with_context("phone", user_input, self.response_context)
            if not is_valid:
                # Generate persona-based error message for invalid phone
                error_context = self._create_dynamic_prompt_context("phone")
                error_context["error_type"] = "invalid_format"
                error_context["user_input"] = user_input
                error_prompt = await self._get_ai_error_response(error_context)
                return error_prompt or get_error_message("phone_invalid")
            
            self.visitor_info["visitor_phone"] = user_input
            return await self._advance_to_step(FlowStep.CONFIRM)
            
        except Exception as e:
            logger.error(f"Error handling phone input: {e}")
            return "Error processing your phone number. Please try again."

    async def _handle_confirmation(self, user_input: str) -> str:
        """Handle confirmation step"""
        try:
            if user_input.lower() in self.VALID_CONFIRMATIONS:
                # User confirmed - proceed with registration
                save_success = await self._save_to_db_with_retry()
                if not save_success:
                    return "Registration failed due to database error. Please try again."
                
                notify_success = await self._notify_admin_with_retry()
                if not notify_success:
                    logger.warning("Admin notification failed, but registration was successful")
                
                self._advance_to_step_sync(FlowStep.COMPLETE)
                
                success_msg = "✅ Registration successful!"
                if self.selected_option == VisitorPurpose.CV_DROP:
                    success_msg += " You're all set to drop off your CV with our HR team."
                elif self.selected_option == VisitorPurpose.INTERVIEW:
                    success_msg += " You're all set for your interview."
                elif self.selected_option == VisitorPurpose.NEW_JOINER:
                    success_msg += " Welcome to the team!"
                
                success_msg += " Admin has been notified of your arrival."
                return success_msg
            else:
                # Show confirmation details again
                return self._generate_confirmation_message()
                
        except Exception as e:
            logger.error(f"Error handling confirmation: {e}")
            return "Error processing confirmation. Please try again."

    async def _advance_to_step(self, next_step: FlowStep) -> str:
        """Advance to the next step and get appropriate prompt"""
        try:
            self.current_step = next_step
            self.visitor_info["current_step"] = next_step.value
            
            if next_step == FlowStep.CONFIRM:
                return self._generate_confirmation_message()
            else:
                return await self._get_ai_prompt_for_step(next_step.value)
                
        except Exception as e:
            logger.error(f"Error advancing to step {next_step}: {e}")
            return "Error proceeding to next step. Please try again."

    def _advance_to_step_sync(self, next_step: FlowStep):
        """Synchronously advance to next step (for completion)"""
        self.current_step = next_step
        self.visitor_info["current_step"] = next_step.value

    def _generate_confirmation_message(self) -> str:
        """Generate confirmation message with visitor details"""
        try:
            purpose_display = self.selected_option.value if self.selected_option else "Not specified"
            
            summary = (
                f"👤 Name: {self.visitor_info.get('visitor_name', 'Not provided')}\n"
                f"🆔 CNIC: {self.visitor_info.get('visitor_cnic', 'Not provided')}\n"
                f"📞 Phone: {self.visitor_info.get('visitor_phone', 'Not provided')}\n"
                f"🏢 Host: {self.HOST_NAME}\n"
                f"🎯 Purpose: {purpose_display}"
            )
            
            return get_confirmation_message().format(details=summary)
            
        except Exception as e:
            logger.error(f"Error generating confirmation message: {e}")
            return "Please confirm your registration details. Type 'yes' to proceed."

    async def _get_ai_prompt_for_step(self, step: str) -> str:
        """Get AI-generated prompt for the current step with persona"""
        try:
            context = self._create_dynamic_prompt_context(step)
            
            # Add additional context for AI
            prompt_instruction = f"""
            Generate a request for {step} information with the following characteristics:
            - Persona: {context['persona']}
            - Visitor purpose: {context['purpose']}
            - Tone: Professional yet friendly, encouraging, supportive
            - Style: Warm but business-appropriate, confidence-building
            - Approach: Treat the {context['persona'].get('visitor_identity', 'visitor')} with respect and professionalism
            - Request: {context['step_context'].get('request_type', step)}
            - Context: {context['step_context'].get('context_note', '')}
            
            Make it feel welcoming and professional, appropriate for HR interactions.
            Show respect for their career journey while keeping it business-friendly.
            Include appropriate emoji if it fits naturally.
            Keep it brief but engaging and confidence-building.
            """
            
            prompt = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.ai.process_visitor_input(prompt_instruction, context)
            )
            return prompt
            
        except Exception as e:
            logger.error(f"Error getting AI prompt for step {step}: {e}")
            
        # Enhanced fallback prompts with persona
        fallback_prompts = {
            "name": f"Great choice! Let's get you registered. What's your full name? 👋",
            "cnic": f"Perfect! Now I'll need your CNIC number for our records. 📝", 
            "phone": f"Almost done! What's your phone number so HR can reach you if needed? 📱",
        }
        return fallback_prompts.get(step, "Please provide the requested information:")

    async def _get_ai_error_response(self, error_context: Dict[str, Any]) -> Optional[str]:
        """Generate AI-based error messages with persona"""
        try:
            error_instruction = f"""
            Generate an error message for {error_context['current_step']} with these details:
            - Persona: {error_context['persona']}
            - Error type: {error_context['error_type']}
            - User input: {error_context.get('user_input', 'empty')}
            - Visitor purpose: {error_context['purpose']}
            
            Tone: Professional, understanding, helpful, encouraging
            Style: Business-appropriate but friendly
            Approach: Acknowledge the mistake politely without being condescending
            Be supportive and give clear guidance on what's needed
            Keep it brief, professional, and confidence-building
            Appropriate for HR/professional setting
            """
            
            error_response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.ai.process_visitor_input(error_instruction, error_context)
            )
            return error_response
            
        except Exception as e:
            logger.error(f"Error generating AI error response: {e}")
            return None

    def _get_purpose_friendly_term(self) -> str:
        """Get a friendly term for the visitor purpose"""
        purpose_terms = {
            VisitorPurpose.CV_DROP: "job seeker",
            VisitorPurpose.INTERVIEW: "candidate", 
            VisitorPurpose.NEW_JOINER: "new team member"
        }
        return purpose_terms.get(self.selected_option, "visitor")

    async def _save_to_db_with_retry(self) -> bool:
        """Save visitor information to database with retry mechanism"""
        for attempt in range(self.MAX_RETRY_ATTEMPTS):
            try:
                from main import get_pg_pool
                pool = await get_pg_pool()
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO visitors (visitor_type, full_name, cnic, phone, email, host, purpose, entry_time, exit_time)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        """,
                        self.selected_option.value if self.selected_option else "",
                        self.visitor_info.get("visitor_name", ""),
                        self.visitor_info.get("visitor_cnic", ""),
                        self.visitor_info.get("visitor_phone", ""),
                        self.visitor_info.get("visitor_email", None),
                        self.HOST_NAME,
                        self.selected_option.value if self.selected_option else "",
                        datetime.utcnow(),
                        None  # exit_time
                    )
                logger.info(f"Successfully saved visitor data: {self.visitor_info.get('visitor_name', 'Unknown')}")
                return True
            except Exception as e:
                logger.error(f"Database save attempt {attempt + 1} failed: {e}")
                if attempt < self.MAX_RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(1)  # Brief delay before retry
        logger.error("All database save attempts failed")
        return False

    async def _notify_admin_with_retry(self) -> bool:
        """Notify admin with retry mechanism"""
        if not self.ai.graph_client:
            logger.warning("No graph client available for admin notification")
            return False
            
        for attempt in range(self.MAX_RETRY_ATTEMPTS):
            try:
                access_token = self.ai.get_system_account_token()
                system_user_id = await self.ai.get_user_id("saadsaad@dpl660.onmicrosoft.com", access_token)
                admin_user_id = await self.ai.get_user_id("admin_IT@dpl660.onmicrosoft.com", access_token)
                chat_id = await self.ai.create_or_get_chat(admin_user_id, system_user_id, access_token)
                
                # Enhanced notification message
                purpose_display = self.selected_option.value if self.selected_option else "Not specified"
                pst = timezone(timedelta(hours=5))
                timestamp = datetime.now(pst).strftime("%d-%m-%Y %I:%M:%S %p")
                
                # For CV/Interview/New Joiner, access level is always L1
                access_level = 'L1'
                message = (
                    f"🚨 <b>{purpose_display} Notification</b><br><br>"
                    "A visitor has arrived for HR/Recruitment. Here are the details:<br><br>"
                    f"👤 <b>Name:</b> {self.visitor_info.get('visitor_name', 'Not provided')}<br>"
                    f"📞 <b>Phone:</b> {self.visitor_info.get('visitor_phone', 'Not provided')}<br>"
                    f"🏢 <b>Host:</b> {self.HOST_NAME}<br>"
                    f"🎯 <b>Purpose:</b> {purpose_display}<br>"
                    f"🔐 <b>Access Level:</b> {access_level}<br>"
                    f"🕒 <b>Time:</b> {timestamp}<br><br>"
                    "Please assist the visitor accordingly. 🤝"
                )
                
                await self.ai.send_message_to_host(chat_id, access_token, message)
                logger.info("Admin notification sent successfully")
                return True
                
            except Exception as e:
                logger.error(f"Admin notification attempt {attempt + 1} failed: {e}")
                if attempt < self.MAX_RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(1)  # Brief delay before retry
                    
        logger.error("All admin notification attempts failed")
        return False

    def get_visitor_summary(self) -> Dict[str, Any]:
        """Get a summary of visitor information for debugging/logging"""
        return {
            "current_step": self.current_step.value if self.current_step else None,
            "selected_option": self.selected_option.value if self.selected_option else None,
            "visitor_info": {
                k: v for k, v in self.visitor_info.items() 
                if k not in ["visitor_cnic"]  # Exclude sensitive data
            },
            "completion_percentage": self._calculate_completion_percentage(),
            "persona_active": bool(self.selected_option)
        }

    def _calculate_completion_percentage(self) -> int:
        """Calculate how much of the flow has been completed"""
        step_order = [FlowStep.SELECT_OPTION, FlowStep.NAME, FlowStep.CNIC, FlowStep.PHONE, FlowStep.CONFIRM, FlowStep.COMPLETE]
        try:
            current_index = step_order.index(self.current_step)
            return int((current_index / (len(step_order) - 1)) * 100)
        except ValueError:
            return 0