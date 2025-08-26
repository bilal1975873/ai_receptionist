import re
import logging
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
from enum import Enum
from flows import validate_name, validate_cnic, validate_phone, validate_with_context, ResponseContext
from prompts import get_error_message, get_dynamic_prompt, get_confirmation_message
import asyncio
import asyncpg
from datetime import timezone, timedelta

# Configure logging
logger = logging.getLogger(__name__)

class SupportService(Enum):
    """Enum for support service types to ensure type safety"""
    PLUMBER = "Plumber"
    ELECTRICIAN = "Electrician"
    CARPENTER = "Carpenter"
    PAINTER = "Painter"
    OTHER = "Other"

class FlowStep(Enum):
    """Enum for flow steps to ensure type safety"""
    SELECT_SERVICE = "select_service"
    OTHER_SERVICE = "other_service"
    NAME = "name"
    CNIC = "cnic"
    PHONE = "phone"
    CONFIRM = "confirm"
    COMPLETE = "complete"

class AdminSupportFlow:
    """
    Enhanced flow handler for Admin Support requests with dynamic personas.
    
    Features:
    - Type-safe enums for steps and service types
    - Dynamic AI personas based on service type
    - Rebel/anti-corporate tone with professionalism
    - Role-specific interactions
    - Comprehensive error handling and logging
    - Input sanitization and validation
    - Retry mechanism for failed operations
    - Better state management
    """
    
    # Class constants
    MAX_RETRY_ATTEMPTS = 3
    VALID_CONFIRMATIONS = {"yes", "y", "confirm", "ok", "proceed"}
    HOST_NAME = "Admin"
    
    def __init__(self, ai, db_collection, visitor_info: Optional[Dict[str, Any]] = None):
        self.ai = ai
    # self.db_collection removed (no longer needed)
        self.visitor_info = visitor_info or {}
        self.response_context = ResponseContext()
        
        # Initialize current step
        current_step_str = self.visitor_info.get("current_step")
        self.current_step = self._get_step_enum(current_step_str) or FlowStep.SELECT_SERVICE
        self.visitor_info["current_step"] = self.current_step.value
        
        # Initialize selected service
        service_str = self.visitor_info.get("service_type")
        self.selected_service = self._get_service_enum(service_str)
        
        logger.info(f"Admin Support Flow initialized with step: {self.current_step}, service: {self.selected_service}")

    def _get_step_enum(self, step_str: Optional[str]) -> Optional[FlowStep]:
        """Safely convert string to FlowStep enum"""
        if not step_str:
            return None
        try:
            return FlowStep(step_str)
        except ValueError:
            logger.warning(f"Invalid step string: {step_str}")
            return None

    def _get_service_enum(self, service_str: Optional[str]) -> Optional[SupportService]:
        """Safely convert string to SupportService enum"""
        if not service_str:
            return None
        try:
            return SupportService(service_str)
        except ValueError:
            logger.warning(f"Invalid service string: {service_str}")
            return None

    def _get_persona_context(self) -> Dict[str, Any]:
        """Generate persona context based on selected service type"""
        if not self.selected_service:
            return {}
            
        # Base persona traits for all maintenance workers
        base_persona = {
            "tone": "casual, friendly, slightly rebellious but professional",
            "style": "anti-corporate, relatable, down-to-earth",
            "approach": "treat the person as a skilled professional, not just a worker",
            "humor_level": "light and appropriate",
            "respect_level": "high - acknowledge their expertise"
        }
        
        # Service-specific persona traits
        service_personas = {
            SupportService.PLUMBER: {
                **base_persona,
                "role_identity": "plumber",
                "expertise_area": "pipes, water systems, and flow dynamics",
                "stereotype_subversion": "intelligent problem-solver, not just a pipe fixer",
                "greeting_style": "fellow professional who deals with pressure (pun intended)",
                "professional_respect": "acknowledge their critical role in infrastructure"
            },
            SupportService.ELECTRICIAN: {
                **base_persona,
                "role_identity": "electrician", 
                "expertise_area": "electrical systems, power, and connections",
                "stereotype_subversion": "technical expert, not just a wire connector",
                "greeting_style": "someone who literally powers the place",
                "professional_respect": "acknowledge their precision and safety expertise"
            },
            SupportService.CARPENTER: {
                **base_persona,
                "role_identity": "carpenter",
                "expertise_area": "wood, construction, and structural work", 
                "stereotype_subversion": "craftsperson and artist, not just a wood cutter",
                "greeting_style": "someone who builds and creates with their hands",
                "professional_respect": "acknowledge their craftsmanship and skill"
            },
            SupportService.PAINTER: {
                **base_persona,
                "role_identity": "painter",
                "expertise_area": "surfaces, colors, and aesthetic transformation",
                "stereotype_subversion": "visual artist and surface specialist, not just paint applicator", 
                "greeting_style": "someone who transforms spaces and brings color to life",
                "professional_respect": "acknowledge their artistic eye and technical skill"
            },
            SupportService.OTHER: {
                **base_persona,
                "role_identity": "maintenance professional",
                "expertise_area": "specialized trade work",
                "stereotype_subversion": "skilled specialist in their field",
                "greeting_style": "fellow professional with unique expertise", 
                "professional_respect": "acknowledge their specialized knowledge"
            }
        }
        
        return service_personas.get(self.selected_service, base_persona)

    def _create_dynamic_prompt_context(self, step: str) -> Dict[str, Any]:
        """Create comprehensive context for AI prompt generation"""
        persona_context = self._get_persona_context()
        
        # Step-specific instructions
        step_contexts = {
            "name": {
                "request_type": "full name",
                "validation_hint": "just need a proper name to get things started",
                "context_note": "for registration and identification purposes"
            },
            "cnic": {
                "request_type": "CNIC number", 
                "validation_hint": "national ID format (like 1234512345671)",
                "context_note": "standard security requirement - nothing personal"
            },
            "phone": {
                "request_type": "phone number",
                "validation_hint": "working contact number", 
                "context_note": "in case admin needs to reach out"
            }
        }
        
        return {
            "visitor_type": "maintenance_professional",
            "current_step": step,
            "persona": persona_context,
            "step_context": step_contexts.get(step, {}),
            "service_type": self.selected_service.value if self.selected_service else "",
            "flow_stage": f"collecting {step} information",
            "communication_goal": "make the professional feel respected and welcomed while getting necessary info"
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
            self.current_step = FlowStep.SELECT_SERVICE
            self.visitor_info["current_step"] = self.current_step.value
            logger.info("Admin Support Flow started")
            
            # Updated main prompt for check-in intent
            return "🛠️ Admin Support – External maintenance personnel reporting in?\n\nWho are you here as?"
            
        except Exception as e:
            logger.error(f"Error starting Admin Support flow: {e}")
            return "Sorry, there was an error starting the check-in. Please try again."

    async def process_input(self, user_input: str) -> str:
        """
        Process user input based on current step with comprehensive error handling
        """
        try:
            # Sanitize input
            clean_input = self._sanitize_input(user_input)
            
            # Sync state
            self._sync_state()
            
            logger.info(f"Processing Admin Support input at step {self.current_step}: {clean_input[:50]}...")
            
            # Route to appropriate handler
            handler_map = {
                FlowStep.SELECT_SERVICE: self._handle_service_selection,
                FlowStep.OTHER_SERVICE: self._handle_other_service_input,
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
            logger.error(f"Error processing Admin Support input: {e}")
            return "Sorry, there was an error processing your input. Please try again."

    def _sync_state(self):
        """Synchronize current step and selected service with visitor_info"""
        current_step_str = self.visitor_info.get("current_step")
        if current_step_str:
            step_enum = self._get_step_enum(current_step_str)
            if step_enum:
                self.current_step = step_enum
        
        service_str = self.visitor_info.get("service_type")
        if service_str:
            service_enum = self._get_service_enum(service_str)
            if service_enum:
                self.selected_service = service_enum

    async def _handle_service_selection(self, user_input: str) -> str:
        """Handle service type selection"""
        try:
            # Try to match input with valid services
            input_lower = user_input.lower()
            
            # Handle numeric selection
            if user_input.isdigit():
                service_index = int(user_input) - 1
                services = [service.value for service in SupportService]
                if 0 <= service_index < len(services):
                    selected_service = services[service_index]
                    self.selected_service = SupportService(selected_service)
                    self.visitor_info["service_type"] = selected_service
                    # Special handling for "Other" service
                    if selected_service == "Other":
                        return await self._advance_to_step(FlowStep.OTHER_SERVICE)
                    else:
                        return await self._advance_to_step(FlowStep.NAME)
            
            # Handle text-based selection
            for service in SupportService:
                if service.value.lower() == input_lower:
                    self.selected_service = service
                    self.visitor_info["service_type"] = service.value
                    if service == SupportService.OTHER:
                        return await self._advance_to_step(FlowStep.OTHER_SERVICE)
                    else:
                        return await self._advance_to_step(FlowStep.NAME)
            
            # Handle "Other" selection with free text
            if input_lower in ["other", "5"]:
                self.selected_service = SupportService.OTHER
                self.visitor_info["service_type"] = "Other"
                return await self._advance_to_step(FlowStep.OTHER_SERVICE)
            
            # If no exact match, provide helpful error
            valid_options = [service.value for service in SupportService]
            return f"Invalid option. Please select one of: {', '.join(valid_options)}"
            
        except Exception as e:
            logger.error(f"Error handling service selection: {e}")
            return "Error processing your selection. Please try again."

    async def _handle_other_service_input(self, user_input: str) -> str:
        """Handle custom service description input"""
        try:
            if not user_input.strip():
                return "Please provide a description of the service you need."
            
            # Store the custom service description
            self.visitor_info["custom_service"] = user_input.strip()
            self.visitor_info["service_type"] = f"Other: {user_input.strip()}"
            return await self._advance_to_step(FlowStep.NAME)
            
        except Exception as e:
            logger.error(f"Error handling other service input: {e}")
            return "Error processing your service description. Please try again."

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
                    return "Support request failed due to database error. Please try again."
                
                notify_success = await self._notify_admin_with_retry()
                if not notify_success:
                    logger.warning("Admin notification failed, but support request was successful")
                
                self._advance_to_step_sync(FlowStep.COMPLETE)
                
                success_msg = "✅ Registration is complete! "
                # success_msg += "You've been successfully registered at reception as external support personnel. "
                if self.selected_service == SupportService.PLUMBER:
                    success_msg += "Your arrival as a plumber has been noted. "
                elif self.selected_service == SupportService.ELECTRICIAN:
                    success_msg += "Your arrival as an electrician has been noted. "
                elif self.selected_service == SupportService.CARPENTER:
                    success_msg += "Your arrival as a carpenter has been noted. "
                elif self.selected_service == SupportService.PAINTER:
                    success_msg += "Your arrival as a painter has been noted. "
                elif self.selected_service == SupportService.OTHER:
                    success_msg += "Your arrival has been noted. "

                success_msg += "The admin has been notified."
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
            purpose_display = self.visitor_info.get("service_type", self.selected_service.value if self.selected_service else "Not specified")
            
            # For admin support, access level is always L2
            access_level = 'L2'
            summary = (
                f"👤 Name: {self.visitor_info.get('visitor_name', 'Not provided')}\n"
                f"🆔 CNIC: {self.visitor_info.get('visitor_cnic', 'Not provided')}\n"
                f"📞 Phone: {self.visitor_info.get('visitor_phone', 'Not provided')}\n"
                f"🏢 Host: {self.HOST_NAME}\n"
                f"🛠️ purpose: {purpose_display}"
            )
            
            # Updated confirmation message for check-in, matching other flows (uses confirm/edit prompt)
            return (
                f"✅ All set! Your check-in has been recorded.\n"
                f"{summary}"
                #f"\n\n🔐 Access Level: {access_level}"
                "\nPress 'confirm' to proceed or 'edit' to make changes."
            )
            
        except Exception as e:
            logger.error(f"Error generating confirmation message: {e}")
            return "Please confirm your check-in details. Type 'yes' to proceed."

    async def _get_ai_prompt_for_step(self, step: str) -> str:
        """Get AI-generated prompt for the current step with persona"""
        try:
            context = self._create_dynamic_prompt_context(step)
            
            # Add additional context for AI
            prompt_instruction = f"""
            Generate a request for {step} information with the following characteristics:
            - Persona: {context['persona']}
            - Service type: {context['service_type']}
            - Tone: Casual, friendly, slightly rebellious but professional
            - Style: Anti-corporate, relatable, down-to-earth
            - Approach: Treat the {context['persona'].get('role_identity', 'professional')} as a skilled expert
            - Request: {context['step_context'].get('request_type', step)}
            - Context: {context['step_context'].get('context_note', '')}
            
            Make it feel like you're talking to a fellow professional, not using corporate speak.
            Show respect for their expertise while keeping it casual and friendly.
            Include appropriate emoji if it fits naturally.
            Keep it brief but engaging.
            """
            
            prompt = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.ai.process_visitor_input(prompt_instruction, context)
            )
            return prompt
            
        except Exception as e:
            logger.error(f"Error getting AI prompt for step {step}: {e}")
            
        # Enhanced fallback prompts with persona
        fallback_prompts = {
            "name": f"Alright, let's get you sorted! What's your name, {self._get_role_friendly_term()}? 👋",
            "cnic": f"Cool, now I need your CNIC number for the paperwork - you know how it is! 📝", 
            "phone": f"Last thing - what's your phone number in case admin needs to reach you? 📱",
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
            - Service type: {error_context['service_type']}
            
            Tone: Casual, understanding, slightly humorous but helpful
            Style: Not corporate - like talking to a friend
            Approach: Acknowledge the mistake without being condescending
            Be encouraging and give clear guidance on what's needed
            Keep it brief and friendly
            """
            
            error_response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.ai.process_visitor_input(error_instruction, error_context)
            )
            return error_response
            
        except Exception as e:
            logger.error(f"Error generating AI error response: {e}")
            return None



    def _get_role_friendly_term(self) -> str:
        """Get a friendly term for the service role"""
        role_terms = {
            SupportService.PLUMBER: "plumber",
            SupportService.ELECTRICIAN: "electrician", 
            SupportService.CARPENTER: "carpenter",
            SupportService.PAINTER: "painter",
            SupportService.OTHER: "pro"
        }
        return role_terms.get(self.selected_service, "professional")

    def _get_pakistan_time(self):
        """Get current time in Pakistan timezone as timezone-naive datetime"""
        import pytz
        # Get Pakistan time and remove timezone info for database storage
        pakistan_tz = pytz.timezone('Asia/Karachi')
        pk_time = datetime.now(pakistan_tz)
        # Return timezone-naive datetime (PostgreSQL will store as-is)
        return pk_time.replace(tzinfo=None)

    async def _save_to_db_with_retry(self) -> bool:
        """Save visitor information to database with retry mechanism (PostgreSQL)"""
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
                        "admin",
                        self.visitor_info.get("visitor_name", ""),
                        self.visitor_info.get("visitor_cnic", ""),
                        self.visitor_info.get("visitor_phone", ""),
                        None,  # email not collected in admin support
                        self.HOST_NAME,
                        self.visitor_info.get("service_type", self.selected_service.value if self.selected_service else ""),
                        self._get_pakistan_time(),
                        None  # exit_time
                    )
                logger.info(f"Successfully saved admin support request: {self.visitor_info.get('visitor_name', 'Unknown')}")
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
                service_display = self.visitor_info.get("service_type", self.selected_service.value if self.selected_service else "Not specified")
                import pytz
                # Get Pakistan time directly for notification timestamp
                pkt = pytz.timezone('Asia/Karachi')  # Pakistan Standard Time
                timestamp = datetime.now(pkt).strftime("%d-%m-%Y %I:%M:%S %p")
                access_level = 'L2'
                message = (
    f"🛠️ <b>Admin Support Arrival Notice</b><br><br>"
    "Someone from the maintenance team has arrived at reception.<br><br>"
    f"👤 <b>Name:</b> {self.visitor_info.get('visitor_name', 'Not provided')}<br>"
    f"📞 <b>Phone:</b> {self.visitor_info.get('visitor_phone', 'Not provided')}<br>"
    f"🔧 <b>Role:</b> {service_display}<br>"
    f"🏢 <b>To Meet:</b> {self.HOST_NAME}<br>"
    f"🔐 <b>Access Level:</b> {access_level}<br>"
    f"🕒 <b>Time:</b> {timestamp}<br><br>"
    "Please receive them accordingly. ✅"
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
            "selected_service": self.selected_service.value if self.selected_service else None,
            "visitor_info": {
                k: v for k, v in self.visitor_info.items() 
                if k not in ["visitor_cnic"]  # Exclude sensitive data
            },
            "completion_percentage": self._calculate_completion_percentage(),
            "persona_active": bool(self.selected_service)
        }

    def _calculate_completion_percentage(self) -> int:
        """Calculate how much of the flow has been completed"""
        step_order = [FlowStep.SELECT_SERVICE, FlowStep.OTHER_SERVICE, FlowStep.NAME, FlowStep.CNIC, FlowStep.PHONE, FlowStep.CONFIRM, FlowStep.COMPLETE]
        try:
            current_index = step_order.index(self.current_step)
            return int((current_index / (len(step_order) - 1)) * 100)
        except ValueError:
            return 0