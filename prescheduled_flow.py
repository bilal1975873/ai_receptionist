import re
from datetime import datetime, timezone, timedelta
from flows import validate_name, validate_cnic, validate_phone, validate_email
from prompts import get_error_message
from ai_integration import AIReceptionist
import asyncio
import pymongo
import hashlib
import uuid

class PreScheduledFlow:
    async def _get_ai_prompt_for_step(self, step: str) -> str:
        """Generate a rebel, anti-corporate, context-aware prompt for each step using AI. Host-related fields are excluded from context."""
        context = {
            "visitor_type": "prescheduled",
            "current_step": step,
            "visitor_name": self.visitor_info.get("visitor_name", ""),
            "visitor_cnic": self.visitor_info.get("visitor_cnic", ""),
            "visitor_phone": self.visitor_info.get("visitor_phone", ""),
            "visitor_email": self.visitor_info.get("visitor_email", ""),
            # Host-related fields are intentionally excluded to prevent AI from hallucinating a host step
        }
        # Custom instruction for each step
        if step == "scheduled_name":
            context["custom_instruction"] = (
                "You are DPL's rebel, anti-corporate AI receptionist. Ask the visitor for their name. "
                "The question must include the word 'name', be witty, bold, and never bureaucratic. "
                "Do not use any preamble or label, just the question."
            )
        elif step == "scheduled_cnic":
            context["custom_instruction"] = (
                "You are DPL's rebel, anti-corporate AI receptionist. Ask the visitor for their CNIC. "
                "The question must include the word 'CNIC', be witty, bold, and never bureaucratic. "
                "Do not use any preamble or label, just the question."
            )
        elif step == "scheduled_phone":
            context["custom_instruction"] = (
                "You are DPL's rebel, anti-corporate AI receptionist. Ask the visitor for their mobile number. "
                "The question must include the word 'number', be witty, bold, and never bureaucratic. "
                "Do not use any preamble or label, just the question."
            )
        elif step == "scheduled_email":
            # Reset context to bare minimum for email step to avoid AI confusion
            context = {
                "current_step": "email",  # Simplified step name
                "format_required": True,
                "custom_instruction": (
                    "- The question for the 'email' step must include the word 'email'."
                )
            }
        else:
            context["custom_instruction"] = (
                "You are DPL's rebel, anti-corporate AI receptionist. Ask for the next required info in the pre-scheduled flow. "
                "Be witty, bold, and never bureaucratic. Do not use any preamble or label, just the question."
            )
        # Debug log: print the context being sent to Bedrock
        #print(f"[DEBUG][AI_PROMPT_CONTEXT][{step}] Context sent to Bedrock: {context}")
        # Use the AI to generate the prompt
        ai_prompt = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.ai.process_visitor_input("", context)
        )
        if not ai_prompt or ai_prompt.strip().lower().startswith("please provide"):
            print(f"[DEBUG][FALLBACK] AI prompt unavailable or fallback for step '{step}', returning error message.")
            return "Sorry, I glitched. Please try again or contact reception."
        return ai_prompt
    def __init__(self, ai: AIReceptionist):
        self.ai = ai
        self.current_step = "scheduled_name"
        self.visitor_info = {
            "visitor_type": "prescheduled",
            "visitor_name": None,
            "visitor_cnic": None,
            "visitor_phone": None,
            "visitor_email": None,
            "host_requested": None,
            "host_confirmed": None,
            "host_email": None,
            "scheduled_meeting": None
        }
        self.employee_selection_mode = False
        self.employee_matches = []
        self.scheduled_meeting_selection_mode = False
        self.scheduled_meeting_options = []
        
        # Define the host accounts to check
        self.host_accounts = [
            {
                "email": "SyedAhmed@DPL660.onmicrosoft.com",
                "object_id": "4cdd94b7-e100-4f49-b577-c5371f7f23fd"
            },
            {
                "email": "WaleedBaqir@DPL660.onmicrosoft.com", 
                "object_id": "eaafd038-972c-4a5e-b5ea-8ebbe84f924c"
            }
        ]

    def _format_meeting_times(self, start: str, end: str):
        """Helper method to format meeting times consistently"""
        start_fmt = start
        end_fmt = end
        
        # Format start time
        if start and 'T' in start:
            try:
                from dateutil.parser import parse
                import pytz
                dt_start = parse(start)
                if dt_start.tzinfo is None:
                    dt_start = dt_start.replace(tzinfo=pytz.UTC)
                dt_start = dt_start.astimezone(pytz.timezone('Asia/Karachi'))
                start_fmt = dt_start.strftime('%b %d, %I:%M %p')
            except Exception:
                start_fmt = start
        
        # Format end time
        if end and 'T' in end:
            try:
                from dateutil.parser import parse
                import pytz
                dt_end = parse(end)
                if dt_end.tzinfo is None:
                    dt_end = dt_end.replace(tzinfo=pytz.UTC)
                dt_end = dt_end.astimezone(pytz.timezone('Asia/Karachi'))
                end_fmt = dt_end.strftime('%I:%M %p')
            except Exception:
                end_fmt = end
        
        # Compose time range string
        if start_fmt and end_fmt:
            time_range = f"{start_fmt} - {end_fmt}"
        else:
            time_range = start_fmt or ''
            
        return time_range, start_fmt, end_fmt

    def _generate_meeting_id(self, meeting):
        """Generate a unique meeting ID with better fallbacks"""
        # Try to get existing ID first
        meeting_id = (
            meeting.get('id') or
            meeting.get('original_event', {}).get('id')
        )
        
        if meeting_id:
            return meeting_id
        
        # Create a more robust fallback ID using hash
        subject = meeting.get('subject', meeting.get('title', ''))
        start_time = meeting.get('start_time', meeting.get('scheduled_time', ''))
        organizer = meeting.get('organizer', {}).get('emailAddress', {}).get('address', '')
        
        # Create a unique string and hash it
        unique_string = f"{subject}-{start_time}-{organizer}"
        hash_id = hashlib.md5(unique_string.encode()).hexdigest()[:12]
        
        return f"generated-{hash_id}"

    async def process_input(self, user_input: str) -> str:
        # Step 1: Name
        if self.current_step == "scheduled_name":
            if not user_input.strip():
                return get_error_message("empty_field")
            if not validate_name(user_input.strip()):
                return get_error_message("name_invalid")
            self.visitor_info["visitor_name"] = user_input.strip()
            self.current_step = "scheduled_cnic"
            ai_prompt = await self._get_ai_prompt_for_step("scheduled_cnic")
            return ai_prompt
        # Step 2: CNIC
        elif self.current_step == "scheduled_cnic":
            if not user_input.strip():
                return get_error_message("empty_field")
            if not validate_cnic(user_input.strip()):
                return get_error_message("cnic_invalid")
            self.visitor_info["visitor_cnic"] = user_input.strip()
            self.current_step = "scheduled_phone"
            ai_prompt = await self._get_ai_prompt_for_step("scheduled_phone")
            return ai_prompt
        # Step 3: Phone
        elif self.current_step == "scheduled_phone":
            if not user_input.strip():
                return get_error_message("empty_field")
            if not validate_phone(user_input.strip()):
                return get_error_message("phone_invalid")
            self.visitor_info["visitor_phone"] = user_input.strip()
            self.current_step = "scheduled_email"
            ai_prompt = await self._get_ai_prompt_for_step("scheduled_email")
            return ai_prompt
        # Step 4: Email - Now directly checks meetings across all host calendars
        elif self.current_step == "scheduled_email":
            if not user_input.strip():
                return get_error_message("empty_field")
            if not validate_email(user_input.strip()):
                return get_error_message("email_invalid")
            self.visitor_info["visitor_email"] = user_input.strip()
            print(f"[DEBUG] Email set to: '{self.visitor_info['visitor_email']}'")
            print(f"[DEBUG] visitor_info after email: {self.visitor_info}")
            self.current_step = "scheduled_meeting"
            return await self._check_meetings_across_hosts()
        
        # Step 5: Meeting selection
        elif self.current_step == "scheduled_meeting":
            if self.scheduled_meeting_selection_mode:
                try:
                    idx = int(user_input.strip()) - 1
                    if idx < 0 or idx >= len(self.scheduled_meeting_options):
                        return "Invalid selection. Please select a valid meeting number."
                    meeting = self.scheduled_meeting_options[idx]
                    self.visitor_info["scheduled_meeting"] = meeting
                    print(f"[DEBUG] Before meeting processing - visitor_info: {self.visitor_info}")

                    # --- Edge case handling for early arrivals only (late check moved to confirmation step) ---
                    from datetime import datetime, timezone, timedelta
                    import pytz
                    from dateutil.parser import parse
                    now = datetime.now(timezone.utc)
                    # Get meeting start time (try all possible keys)
                    start = (
                        meeting.get('scheduled_time') or
                        meeting.get('start_time') or
                        meeting.get('original_event', {}).get('start', {}).get('dateTime') or
                        ''
                    )
                    if start:
                        try:
                            dt_start = parse(start)
                            if dt_start.tzinfo is None:
                                dt_start = dt_start.replace(tzinfo=pytz.UTC)
                            # Calculate time difference in minutes - keep this for notification purposes
                            diff_minutes = (now - dt_start).total_seconds() / 60
                            # Note: We keep calculating the time difference for admin notifications,
                            # but we allow all visitors to proceed regardless of timing
                        except Exception as e:
                            print(f"[DEBUG] Error parsing meeting start time: {e}")

                    # Set host_confirmed and host_email from calendar owner name
                    host_from_meeting = meeting.get("calendar_owner_name", meeting.get("calendar_owner_email", "N/A"))
                    self.visitor_info["host_confirmed"] = host_from_meeting
                    self.visitor_info["host_email"] = meeting.get("calendar_owner_email", "N/A")
                    self.visitor_info["host_requested"] = host_from_meeting
                    print(f"[DEBUG] Host confirmed: '{self.visitor_info['host_confirmed']}'")
                    print(f"[DEBUG] Host email: '{self.visitor_info['host_email']}'")
                    print(f"[DEBUG] After meeting processing - visitor_info: {self.visitor_info}")
                    self.current_step = "scheduled_confirm"
                    return self._get_meeting_confirmation(meeting)
                except Exception as e:
                    print(f"[DEBUG] Error in meeting selection: {e}")
                    return "Invalid input. Please enter the meeting number."
            
            # Handle guest fallback if no meetings
            if user_input.strip() == "1":
                self.visitor_info["visitor_type"] = "guest"
                self.current_step = "purpose"
                return "What is the purpose of your visit?"
            elif user_input.strip() == "2":
                self.current_step = "scheduled_email"
                return "Please provide your email address."
            
            return await self._check_meetings_across_hosts()
        
        # Step 6: Confirmation
        elif self.current_step == "scheduled_confirm":
            if user_input.strip() == "1":
                self.visitor_info["visitor_type"] = "guest"
                self.current_step = "purpose"
                return "What is the purpose of your visit?"
            elif user_input.strip() == "2":
                self.current_step = "scheduled_email"
                return "Please provide your email address."
            
            if user_input.strip().lower() == "confirm":
                await self._finalize_registration()
                self.current_step = "complete"
                return "Registration successful. Rebel presence incoming — host's been warned"
            elif user_input.strip().lower() == "edit":
                self.current_step = "scheduled_name"
                # Return AI-generated prompt for name step
                return await self._get_ai_prompt_for_step("scheduled_name")
            else:
                meeting = self.visitor_info.get("scheduled_meeting")
                return self._get_meeting_confirmation(meeting)
        
        # Step 7: Complete
        elif self.current_step == "complete":
            if user_input.strip().lower() in ["yes", "y"]:
                self.__init__(self.ai)
                return "Please select your visitor type:\n1. Guest\n2. Vendor\n3. Pre-scheduled meeting"
            else:
                return "Thank you for using the DPL Receptionist."
        else:
            return "Invalid step. Please start again."

    async def _check_meetings_across_hosts(self):
        """Check meetings across all host calendars for the visitor's email - OPTIMIZED VERSION"""
        print(f"[DEBUG] Checking meetings across all hosts for email: {self.visitor_info['visitor_email']}")
        
        current_time = datetime.now(timezone.utc)
        
        # Create all tasks for parallel execution
        tasks = []
        for host_account in self.host_accounts:
            task = self.ai.get_scheduled_meetings(
                host_account["email"],
                self.visitor_info["visitor_email"],
                current_time
            )
            tasks.append((host_account, task))
        
        # Execute all API calls in parallel
        start_time = datetime.now()
        results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
        end_time = datetime.now()
        
        print(f"[DEBUG] Parallel API calls completed in {(end_time - start_time).total_seconds():.2f} seconds")
        
        # Process results
        all_meetings = []
        visitor_email = self.visitor_info["visitor_email"].lower()  # Case-insensitive comparison
        
        for (host_account, _), meetings in zip(tasks, results):
            try:
                if isinstance(meetings, Exception):
                    print(f"[DEBUG] Error checking calendar for {host_account['email']}: {meetings}")
                    continue
                    
                if meetings:
                    print(f"[DEBUG] Found {len(meetings)} total meetings for host {host_account['email']}")
                    
                    for meeting in meetings:
                        print(f"[DEBUG] Checking meeting: {meeting.get('subject', 'No Subject')}")
                        #print(f"[DEBUG] Raw meeting data: {meeting}")
                        is_participant = False
                        
                        # First check in the original_event if it exists
                        original_event = meeting.get('original_event', {})
                        
                        # Check attendees in original_event first, then fall back to root
                        attendees = original_event.get('attendees', meeting.get('attendees', []))
                        print(f"[DEBUG] Attendees: {attendees}")
                        
                        for attendee in attendees:
                            print(f"[DEBUG] Checking attendee: {attendee}")
                            attendee_email = None
                            
                            if isinstance(attendee, dict):
                                # Microsoft Graph API format
                                if isinstance(attendee.get('emailAddress'), dict):
                                    attendee_email = attendee['emailAddress'].get('address')
                                    print(f"[DEBUG] Found emailAddress.address: {attendee_email}")
                                # Other possible formats
                                else:
                                    possible_email_fields = ['email', 'address', 'upn', 'mail']
                                    for field in possible_email_fields:
                                        if field in attendee:
                                            attendee_email = attendee[field]
                                            print(f"[DEBUG] Found email in field {field}: {attendee_email}")
                                            break
                            elif isinstance(attendee, str):
                                attendee_email = attendee
                                print(f"[DEBUG] Found string email: {attendee_email}")
                            
                            if attendee_email:
                                print(f"[DEBUG] Comparing {attendee_email.lower()} with {visitor_email}")
                                if attendee_email.lower() == visitor_email:
                                    print(f"[DEBUG] Found matching attendee email: {attendee_email}")
                                    is_participant = True
                                    break
                        
                        # Check organizer in original_event first, then fall back to root
                        if not is_participant:
                            organizer = original_event.get('organizer', meeting.get('organizer', {}))
                            print(f"[DEBUG] Checking organizer: {organizer}")
                            organizer_email = None
                            
                            if isinstance(organizer, dict):
                                if isinstance(organizer.get('emailAddress'), dict):
                                    organizer_email = organizer['emailAddress'].get('address')
                                    print(f"[DEBUG] Found organizer emailAddress.address: {organizer_email}")
                                elif 'email' in organizer:
                                    organizer_email = organizer['email']
                                    print(f"[DEBUG] Found organizer email: {organizer_email}")
                            
                            if organizer_email:
                                print(f"[DEBUG] Comparing organizer {organizer_email.lower()} with {visitor_email}")
                                if organizer_email.lower() == visitor_email:
                                    print(f"[DEBUG] Found matching organizer email: {organizer_email}")
                                    is_participant = True
                        
                        if is_participant:
                            # Add meeting to results only if visitor is a participant
                            meeting["calendar_owner_email"] = host_account["email"]
                            meeting["calendar_owner_name"] = host_account.get("name", host_account["email"].split('@')[0])
                            # Set friendly names for specific hosts
                            if host_account["email"] == "SyedAhmed@DPL660.onmicrosoft.com":
                                meeting["calendar_owner_name"] = "Syed Ahmed"
                            elif host_account["email"] == "WaleedBaqir@DPL660.onmicrosoft.com":
                                meeting["calendar_owner_name"] = "Waleed Baqir"
                            all_meetings.append(meeting)
                else:
                    print(f"[DEBUG] No meetings found for host {host_account['email']}")
            except Exception as e:
                print(f"[DEBUG] Error processing results for {host_account['email']}: {e}")
                continue
        
        # Remove duplicates using meeting ID
        unique_meetings = []
        seen_meetings = set()
        
        for meeting in all_meetings:
            meeting_id = self._generate_meeting_id(meeting)
            if meeting_id not in seen_meetings:
                seen_meetings.add(meeting_id)
                unique_meetings.append(meeting)
        
        print(f"[DEBUG] Total unique meetings found: {len(unique_meetings)}")
        
        if not unique_meetings:
            return "No meetings found with your email address for today. Would you like to check in as a guest instead?\n1. Yes, check in as guest\n2. No, re-enter email address"
        
        self.scheduled_meeting_selection_mode = True
        self.scheduled_meeting_options = unique_meetings
        
        # Format meeting options
        options = "Please select your meeting from the list below by number:\n"
        for idx, meeting in enumerate(unique_meetings, 1):
            # Use the same robust subject extraction as in confirmation
            original_event = meeting.get('original_event', {})
            subject = (
                meeting.get('subject') or 
                meeting.get('title') or
                meeting.get('name') or 
                meeting.get('purpose') or 
                meeting.get('bodyPreview') or 
                original_event.get('subject') or 
                original_event.get('title') or 
                original_event.get('name') or 
                original_event.get('purpose') or 
                'N/A'
            )
            
            # Use the same robust start/end time extraction as in confirmation
            start = (
                meeting.get('start_time') or
                (meeting.get('start', {}).get('dateTime') if isinstance(meeting.get('start'), dict) else None) or
                meeting.get('startDateTime') or
                original_event.get('start', {}).get('dateTime') or
                ''
            )
            
            end = (
                meeting.get('end_time') or
                (meeting.get('end', {}).get('dateTime') if isinstance(meeting.get('end'), dict) else None) or
                meeting.get('endDateTime') or
                original_event.get('end', {}).get('dateTime') or
                ''
            )
            
            time_range, _, _ = self._format_meeting_times(start, end)
            host_name = meeting.get("calendar_owner_name", "Unknown Host")
            options += f"{idx}. {subject} | {time_range} | Host: {host_name}\n"
        
        return options

    def _get_meeting_confirmation(self, meeting):
        if not meeting:
            return "No meeting selected. Please select a meeting."

        print("[DEBUG] meeting object:", meeting)
        print("[DEBUG] visitor_info FULL:", self.visitor_info)
        print("[DEBUG][BACKEND] visitor_info at confirmation:", self.visitor_info)

        # Extract visitor information
        visitor = self.visitor_info.get("visitor_name") or "N/A"
        cnic = self.visitor_info.get("visitor_cnic") or "N/A"
        phone = self.visitor_info.get("visitor_phone") or "N/A"
        email = self.visitor_info.get("visitor_email") or "N/A"
        print(f"[DEBUG][BACKEND] visitor_email at confirmation: {email}")
        
        # Extract host information
        host = self.visitor_info.get("host_confirmed") or "N/A"
        organizer = meeting.get("organizer", {})
        email_address = organizer.get("emailAddress", {})
        
        if (not host or host == "N/A"):
            host = (
                email_address.get("name") or
                organizer.get("displayName") or
                organizer.get("name") or
                meeting.get("host") or
                self.visitor_info.get("host_requested") or
                "N/A"
            )

        # Extract subject with all possible fallbacks
        subject = (
            meeting.get('subject') or
            meeting.get('title') or
            meeting.get('name') or
            meeting.get('purpose') or
            meeting.get('bodyPreview') or
            meeting.get('original_event', {}).get('subject') or
            meeting.get('original_event', {}).get('title') or
            meeting.get('original_event', {}).get('name') or
            meeting.get('original_event', {}).get('purpose') or
            'N/A'
        )

        # Extract start and end time
        start = (
            meeting.get('start_time') or
            (meeting.get('start', {}).get('dateTime') if isinstance(meeting.get('start'), dict) else None) or
            meeting.get('startDateTime') or
            meeting.get('original_event', {}).get('start', {}).get('dateTime') or
            ''
        )
        end = (
            meeting.get('end_time') or
            (meeting.get('end', {}).get('dateTime') if isinstance(meeting.get('end'), dict) else None) or
            meeting.get('endDateTime') or
            meeting.get('original_event', {}).get('end', {}).get('dateTime') or
            ''
        )

        # Use the helper method for consistent formatting
        time_range, start_fmt, end_fmt = self._format_meeting_times(start, end)

        # --- Arrival time logic: decide notification and message target ---
        from datetime import datetime, timezone
        import pytz
        from dateutil.parser import parse
        now = datetime.now(timezone.utc)
        arrival_status = "normal"  # can be 'normal', 'late', 'early'
        late_message = ""
        
        if start:
            try:
                dt_start = parse(start)
                if dt_start.tzinfo is None:
                    dt_start = dt_start.replace(tzinfo=pytz.UTC)
                diff_minutes = (now - dt_start).total_seconds() / 60
                if diff_minutes < -30:
                    arrival_status = "early"
                elif diff_minutes > 60:
                    arrival_status = "late"
                else:
                    arrival_status = "normal"
            except Exception as e:
                print(f"[DEBUG] Error parsing meeting start time for arrival status: {e}")

        # --- Unified, line-by-line confirmation message ---
        confirm_message = (
            f"Please review your information.\n"
            f"Type 'confirm' to proceed or 'edit' to start over.\n"
            f"Name: {visitor}\n"
            f"CNIC: {cnic}\n"
            f"Phone: {phone}\n"
            f"Email: {email}\n"
            f"Host: {host}\n"
            f"Meeting: {subject} | {time_range}\n"
        )
        
        if arrival_status == "late":
            late_message = "You are more than 1 hour late for your meeting. We are notifying the admin.\n"
            confirm_message += late_message
            
        return confirm_message

    async def insert_prescheduled_visitor_to_db(self, visitor_type, full_name, cnic, phone, host, purpose, is_group_visit=False, group_members=None, total_members=1, email=None):
        from main import visitors_collection  # local import to avoid circular import
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

    async def _finalize_registration(self):
        meeting = self.visitor_info["scheduled_meeting"]
        # Always set host_confirmed and host_email from the selected meeting's organizer (calendar owner)
        organizer = meeting.get("organizer", {})
        self.visitor_info["host_confirmed"] = (
            organizer.get("displayName") or 
            organizer.get("name") or 
            organizer.get("emailAddress", {}).get("name") or 
            meeting.get("host") or 
            self.visitor_info.get("host_requested") or 
            "N/A"
        )
        self.visitor_info["host_email"] = (
            organizer.get("emailAddress", {}).get("address") or 
            organizer.get("email") or 
            meeting.get("host_email") or 
            "N/A"
        )
        # Use robust subject extraction for purpose
        subject = (
            meeting.get('subject') or
            meeting.get('title') or
            meeting.get('name') or
            meeting.get('purpose') or
            meeting.get('bodyPreview') or
            meeting.get('original_event', {}).get('subject') or
            meeting.get('original_event', {}).get('title') or
            meeting.get('original_event', {}).get('name') or
            meeting.get('original_event', {}).get('purpose') or
            ''
        )
        await self.insert_prescheduled_visitor_to_db(
            visitor_type="prescheduled",
            full_name=self.visitor_info["visitor_name"],
            cnic=self.visitor_info["visitor_cnic"],
            phone=self.visitor_info["visitor_phone"],
            host=self.visitor_info["host_confirmed"],
            purpose=subject,
            is_group_visit=False,
            email=self.visitor_info["visitor_email"]
        )
        
        # --- Extract subject (purpose) and formatted time range for admin notification ---
        start = (
            meeting.get('start_time') or
            (meeting.get('start', {}).get('dateTime') if isinstance(meeting.get('start'), dict) else None) or
            meeting.get('startDateTime') or
            meeting.get('original_event', {}).get('start', {}).get('dateTime') or
            ''
        )
        end = (
            meeting.get('end_time') or
            (meeting.get('end', {}).get('dateTime') if isinstance(meeting.get('end'), dict) else None) or
            meeting.get('endDateTime') or
            meeting.get('original_event', {}).get('end', {}).get('dateTime') or
            ''
        )
        
        # Use the helper method for consistent formatting
        time_range, start_fmt, end_fmt = self._format_meeting_times(start, end)
        
        # Always send notification to admin
        from datetime import datetime, timezone
        import pytz
        from dateutil.parser import parse
        now = datetime.now(timezone.utc)
        arrival_status = "normal"
        if start:
            try:
                dt_start = parse(start)
                if dt_start.tzinfo is None:
                    dt_start = dt_start.replace(tzinfo=pytz.UTC)
                diff_minutes = (now - dt_start).total_seconds() / 60
                if diff_minutes < -30:
                    arrival_status = "early"
                elif diff_minutes > 60:
                    arrival_status = "late"
                else:
                    arrival_status = "normal"
            except Exception as e:
                print(f"[DEBUG] Error parsing meeting start time for arrival status in finalize: {e}")
        access_token = self.ai.get_system_account_token()
        system_user_id = await self.ai.get_user_id(self.ai._system_account_email, access_token)
        ADMIN_EMAIL = getattr(self.ai, 'admin_email', None) or 'admin_IT@dpl660.onmicrosoft.com'
        admin_user_id = await self.ai.get_user_id(ADMIN_EMAIL, access_token)
        chat_id = await self.ai.create_or_get_chat(admin_user_id, system_user_id, access_token)
        # Always set arrival_fmt using Asia/Karachi timezone
        pk_tz = pytz.timezone('Asia/Karachi')
        arrival_fmt = now.astimezone(pk_tz).strftime('%b %d, %I:%M %p')
        if arrival_status == "late":
            dt_start = parse(start)
            if dt_start.tzinfo is None:
                dt_start = dt_start.replace(tzinfo=pytz.UTC)
            start_fmt_admin = dt_start.astimezone(pk_tz).strftime('%b %d, %I:%M %p')
            visitor_name = self.visitor_info['visitor_name']
            visitor_email = self.visitor_info['visitor_email']
            admin_message = (
                f"⚠️ <b>Late Visitor Arrival Alert</b><br><br>"
                f"A visitor has arrived more than 1 hour late for their scheduled meeting.<br><br>"
                f"👤 Name: {visitor_name}<br>"
                f"📧 Email: {visitor_email}<br>"
                f"👨‍💼 Host: {self.visitor_info['host_confirmed']}<br>"
                f"🎯 Meeting: {subject}<br>"
                f"🕓 Scheduled Time: {start_fmt_admin}<br>"
                f"🚶 Arrival Time: {arrival_fmt}"
            )
            await self.ai.send_message_to_host(chat_id, access_token, admin_message)
        elif arrival_status == "early":
            # Early arrival notification
            dt_start = parse(start)
            if dt_start.tzinfo is None:
                dt_start = dt_start.replace(tzinfo=pytz.UTC)
            start_fmt_admin = dt_start.astimezone(pk_tz).strftime('%b %d, %I:%M %p')
            visitor_name = self.visitor_info['visitor_name']
            visitor_email = self.visitor_info['visitor_email']
            admin_message = (
                f"⏰ <b>Early Visitor Arrival Alert</b><br><br>"
                f"A visitor has arrived more than 30 minutes early for their scheduled meeting.<br><br>"
                f"👤 Name: {visitor_name}<br>"
                f"📧 Email: {visitor_email}<br>"
                f"👨‍💼 Host: {self.visitor_info['host_confirmed']}<br>"
                f"🎯 Meeting: {subject}<br>"
                f"🕓 Scheduled Time: {start_fmt_admin}<br>"
                f"🚶 Arrival Time: {arrival_fmt}"
            )
            await self.ai.send_message_to_host(chat_id, access_token, admin_message)
            # For early arrivals, only notify admin, not host
        else:
            # Normal arrival notification
            # For prescheduled, access level is always L2
            access_level = 'L2'
            message = (
                "🔔 <b>Scheduled Visitor Arrival Notification</b><br><br>"
                "A scheduled visitor has arrived. Here are the details:<br><br>"
                f"👤 Name: {self.visitor_info['visitor_name']}<br>"
                f"📞 Phone: {self.visitor_info['visitor_phone']}<br>"
                f"📧 Email: {self.visitor_info['visitor_email']}<br>"
                f"🕓 Scheduled Time: {time_range}<br>"
                f"🚶 Arrival Time: {arrival_fmt}<br>"
                f"👨‍💼 Host: {self.visitor_info['host_confirmed']}<br>"
                f"🎯 Subject: {subject}<br>"
                f"🔐 Access Level: {access_level}"
            )
            await self.ai.send_message_to_host(chat_id, access_token, message)
            # For normal arrivals, notify both admin and host