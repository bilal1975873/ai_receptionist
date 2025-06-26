# Pre-scheduled flow for DPL Receptionist Bot
# This flow is separated from main.py as requested

import re
from datetime import datetime, timezone, timedelta
from flows import validate_name, validate_cnic, validate_phone, validate_email
from prompts import get_error_message
from ai_integration import AIReceptionist
import asyncio
import pymongo

class PreScheduledFlow:
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

    async def process_input(self, user_input: str) -> str:
        # Step 1: Name
        if self.current_step == "scheduled_name":
            if not user_input.strip():
                return get_error_message("empty")
            if not validate_name(user_input.strip()):
                return get_error_message("name")
            self.visitor_info["visitor_name"] = user_input.strip()
            self.current_step = "scheduled_cnic"
            return "Please provide your CNIC number in the format: 12345-1234567-1."
        # Step 2: CNIC
        elif self.current_step == "scheduled_cnic":
            if not user_input.strip():
                return get_error_message("empty")
            if not validate_cnic(user_input.strip()):
                return get_error_message("cnic")
            self.visitor_info["visitor_cnic"] = user_input.strip()
            self.current_step = "scheduled_phone"
            return "Please provide your phone number in the format: 03001234567."
        # Step 3: Phone
        elif self.current_step == "scheduled_phone":
            if not user_input.strip():
                return get_error_message("empty")
            if not validate_phone(user_input.strip()):
                return get_error_message("phone")
            self.visitor_info["visitor_phone"] = user_input.strip()
            self.current_step = "scheduled_email"
            return "Please provide your email address."
        # Step 4: Email
        elif self.current_step == "scheduled_email":
            if not user_input.strip():
                return get_error_message("empty")
            if not validate_email(user_input.strip()):
                return get_error_message("email")
            self.visitor_info["visitor_email"] = user_input.strip()
            print(f"[DEBUG] Email set to: '{self.visitor_info['visitor_email']}'")
            print(f"[DEBUG] visitor_info after email: {self.visitor_info}")
            self.current_step = "scheduled_host"
            return "Please enter the name of the person you are scheduled to meet (host)."
        # Step 5: Host selection (with fuzzy search)
        elif self.current_step == "scheduled_host":
            # If user enters '0' when not in selection mode, always prompt for a new name
            if not self.employee_selection_mode and user_input.strip() == "0":
                return "Please enter the name of the person you are scheduled to meet (host)."
            if self.employee_selection_mode:
                if user_input == "0":
                    self.employee_selection_mode = False
                    self.employee_matches = []
                    self.current_step = "scheduled_host"
                    return "Please enter the name of the person you are scheduled to meet (host)."
                # If not a valid number, treat as a new host search
                if not user_input.isdigit() or int(user_input) < 1 or int(user_input) > len(self.employee_matches):
                    self.employee_selection_mode = False
                    self.employee_matches = []
                    self.current_step = "scheduled_host"
                    return "Please enter the name of the person you are scheduled to meet (host)."
                selected = await self.ai.handle_employee_selection(user_input, self.employee_matches)
                if selected:
                    self.visitor_info["host_confirmed"] = selected["displayName"]
                    self.visitor_info["host_email"] = selected["email"]
                    self.visitor_info["host_requested"] = selected["displayName"]  # Store the requested host too
                    print(f"[DEBUG] Host confirmed: '{self.visitor_info['host_confirmed']}'")
                    print(f"[DEBUG] Host email: '{self.visitor_info['host_email']}'")
                    print(f"[DEBUG] visitor_info after host selection: {self.visitor_info}")
                    self.employee_selection_mode = False
                    self.employee_matches = []
                    self.current_step = "scheduled_meeting"
                    return await self._fetch_and_show_meetings()
                else:
                    return "Invalid selection. Please try again."
            # Not in selection mode, do fuzzy search
            matches = await self.ai.search_employee(user_input.strip())
            if not matches:
                return "No matching host found. Please try again."
            if isinstance(matches, dict):
                self.employee_selection_mode = True
                self.employee_matches = [matches]
                options = "I found the following match. Please select by number:\n"
                emp = matches
                options += f"1. {emp['displayName']} ({emp['email']})\n"
                options += "0. Re-enter host name"
                return options
            if len(matches) == 1:
                self.employee_selection_mode = True
                self.employee_matches = matches
                options = "I found the following match. Please select by number:\n"
                emp = matches[0]
                options += f"1. {emp['displayName']} ({emp['email']})\n"
                options += "0. Re-enter host name"
                return options
            else:
                self.employee_selection_mode = True
                self.employee_matches = matches
                options = "Please select your host by number:\n"
                for idx, emp in enumerate(matches, 1):
                    options += f"{idx}. {emp['displayName']} ({emp['email']})\n"
                options += "0. Re-enter host name"
                return options
        # Step 6: Meeting selection
        elif self.current_step == "scheduled_meeting":
            if self.scheduled_meeting_selection_mode:
                try:
                    idx = int(user_input.strip()) - 1
                    if idx < 0 or idx >= len(self.scheduled_meeting_options):
                        return "Invalid selection. Please select a valid meeting number."
                    meeting = self.scheduled_meeting_options[idx]
                    self.visitor_info["scheduled_meeting"] = meeting
                    
                    print(f"[DEBUG] Before meeting processing - visitor_info: {self.visitor_info}")
                    
                    # --- FIXED: Don't overwrite existing host and email info ---
                    # Only extract from meeting if we don't already have the info
                    organizer = meeting.get("organizer", {})
                    
                    # Keep the host info from the employee selection step
                    # Only fallback to meeting organizer if we somehow lost it
                    if not self.visitor_info.get("host_confirmed"):
                        host_from_meeting = (
                            organizer.get("displayName") or 
                            organizer.get("name") or 
                            organizer.get("emailAddress", {}).get("name") or
                            meeting.get("host") or 
                            "N/A"
                        )
                        self.visitor_info["host_confirmed"] = host_from_meeting
                        print(f"[DEBUG] Set host from meeting: '{host_from_meeting}'")
                    else:
                        print(f"[DEBUG] Keeping existing host: '{self.visitor_info['host_confirmed']}'")
                    
                    # Keep the host email from the employee selection step
                    # Only fallback to meeting organizer if we somehow lost it
                    if not self.visitor_info.get("host_email"):
                        email_from_meeting = (
                            organizer.get("emailAddress", {}).get("address") or 
                            organizer.get("email") or 
                            meeting.get("host_email") or 
                            "N/A"
                        )
                        self.visitor_info["host_email"] = email_from_meeting
                        print(f"[DEBUG] Set host email from meeting: '{email_from_meeting}'")
                    else:
                        print(f"[DEBUG] Keeping existing host email: '{self.visitor_info['host_email']}'")
                    
                    # Keep the visitor email from the form step
                    # Only check attendees if we somehow lost it
                    if not self.visitor_info.get("visitor_email"):
                        attendees = meeting.get("attendees", [])
                        if attendees:
                            attendee = attendees[0]
                            email_from_attendees = (
                                attendee.get("emailAddress", {}).get("address") or 
                                attendee.get("email") or 
                                "N/A"
                            )
                            self.visitor_info["visitor_email"] = email_from_attendees
                            print(f"[DEBUG] Set visitor email from attendees: '{email_from_attendees}'")
                    else:
                        print(f"[DEBUG] Keeping existing visitor email: '{self.visitor_info['visitor_email']}'")
                    
                    print(f"[DEBUG] After meeting processing - visitor_info: {self.visitor_info}")
                    
                    self.current_step = "scheduled_confirm"
                    return self._get_meeting_confirmation(meeting)
                except Exception as e:
                    print(f"[DEBUG] Error in meeting selection: {e}")
                    return "Invalid input. Please enter the meeting number."
            # Not in selection mode, fetch meetings
            # Handle guest fallback if no meetings
            if user_input.strip() == "1":
                self.visitor_info["visitor_type"] = "guest"
                self.current_step = "purpose"
                return "What is the purpose of your visit?"
            elif user_input.strip() == "2":
                self.current_step = "scheduled_host"
                return "Please enter the name of the person you are scheduled to meet (host)."
            return await self._fetch_and_show_meetings()
        # Step 7: Confirmation
        elif self.current_step == "scheduled_confirm":
            if user_input.strip() == "1":
                self.visitor_info["visitor_type"] = "guest"
                self.current_step = "purpose"
                return "What is the purpose of your visit?"
            elif user_input.strip() == "2":
                self.current_step = "scheduled_host"
                return "Please enter the name of the person you are scheduled to meet (host)."
            if user_input.strip().lower() == "confirm":
                await self._finalize_registration()
                self.current_step = "complete"
                return "Registration successful. Rebel presence incoming — host’s been warned"
            elif user_input.strip().lower() == "edit":
                self.current_step = "scheduled_name"
                return "Let's start over. Please enter your name."
            else:
                meeting = self.visitor_info.get("scheduled_meeting")
                return self._get_meeting_confirmation(meeting)
        # Step 8: Complete
        elif self.current_step == "complete":
            if user_input.strip().lower() in ["yes", "y"]:
                self.__init__(self.ai)
                return "Please select your visitor type:\n1. Guest\n2. Vendor\n3. Pre-scheduled meeting"
            else:
                return "Thank you for using the DPL Receptionist."
        else:
            return "Invalid step. Please start again."

    async def _fetch_and_show_meetings(self):
        # Pass all required arguments to get_scheduled_meetings
        meetings = await self.ai.get_scheduled_meetings(
            self.visitor_info["host_email"],
            self.visitor_info["visitor_name"],
            datetime.now(timezone.utc)
        )
        if not meetings:
            return "No meetings found for this host today. Would you like to check in as a guest instead?\n1. Yes, check in as guest\n2. No, re-enter host name"
        self.scheduled_meeting_selection_mode = True
        self.scheduled_meeting_options = meetings
        options = "Please select your meeting from the list below by number:\n"
        for idx, meeting in enumerate(meetings, 1):
            # Use subject and start time, fallback to 'No subject' if missing
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
                'No subject'
            )
            # Try all possible keys for start and end time
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
            # Format start and end time for readability if possible
            if start and 'T' in start:
                try:
                    from dateutil.parser import parse
                    dt_start = parse(start)
                    start_fmt = dt_start.strftime('%b %d, %I:%M %p')
                except Exception:
                    start_fmt = start
            else:
                start_fmt = start
            if end and 'T' in end:
                try:
                    from dateutil.parser import parse
                    dt_end = parse(end)
                    end_fmt = dt_end.strftime('%I:%M %p')
                except Exception:
                    end_fmt = end
            else:
                end_fmt = end
            # Compose time range string
            if start_fmt and end_fmt:
                time_range = f"{start_fmt} - {end_fmt}"
            else:
                time_range = start_fmt or ''
            options += f"{idx}. {subject} | {time_range}\n"
        # If no meetings, offer guest check-in
        if not meetings:
            options += "No meetings found for this host today. Would you like to check in as a guest instead?\n1. Yes, check in as guest\n2. No, re-enter host name"
        return options

    def _get_meeting_confirmation(self, meeting):
        if not meeting:
            return "No meeting selected. Please select a meeting."
        
        print("[DEBUG] meeting object:", meeting)
        print("[DEBUG] visitor_info FULL:", self.visitor_info)
        
        # --- FIXED: Use the stored visitor info first, then fallback to meeting data ---
        
        # Use the visitor name and phone from form input
        visitor = self.visitor_info.get("visitor_name") or "N/A"
        phone = self.visitor_info.get("visitor_phone") or "N/A"
        
        # Use the visitor email we stored during form input
        email = self.visitor_info.get("visitor_email") or "N/A"
        print(f"[DEBUG] visitor_email from visitor_info: '{email}'")
        
        # Use the host info we stored during employee selection
        host = self.visitor_info.get("host_confirmed") or "N/A"
        host_email = self.visitor_info.get("host_email") or "N/A"
        print(f"[DEBUG] host_confirmed from visitor_info: '{host}'")
        print(f"[DEBUG] host_email from visitor_info: '{host_email}'")
        
        # If we still have N/A values, let's check if they're actually None or empty strings
        if email == "N/A" or not email:
            print("[DEBUG] Email is N/A or empty, checking visitor_info again...")
            email = self.visitor_info.get("visitor_email")
            if email is None or email == "":
                email = "N/A"
            print(f"[DEBUG] After recheck, email: '{email}'")
        
        if host == "N/A" or not host:
            print("[DEBUG] Host is N/A or empty, checking visitor_info again...")
            host = self.visitor_info.get("host_confirmed")
            if host is None or host == "":
                host = "N/A"
            print(f"[DEBUG] After recheck, host: '{host}'")
        
        print(f"[DEBUG] Final values - visitor: {visitor}, phone: {phone}, email: {email}, host: {host}")
        
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
        
        # Extract and format start and end time
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
        
        # Format start and end time for readability if possible
        if start and 'T' in start:
            try:
                from dateutil.parser import parse
                dt_start = parse(start)
                start_fmt = dt_start.strftime('%b %d, %I:%M %p')
            except Exception:
                start_fmt = start
        else:
            start_fmt = start or 'N/A'
        if end and 'T' in end:
            try:
                from dateutil.parser import parse
                dt_end = parse(end)
                end_fmt = dt_end.strftime('%I:%M %p')
            except Exception:
                end_fmt = end
        else:
            end_fmt = end or ''
        
        # Compose time range string
        if start_fmt and end_fmt:
            time_range = f"{start_fmt} - {end_fmt}"
        else:
            time_range = start_fmt or ''
        
        # Final confirmation message
        return (
            f"Please review your information.\n"
            f"Confirmation:\nVisitor: {visitor}\nPhone: {phone}\nEmail: {email}\nHost: {host}\nMeeting: {subject} | {time_range}\n"
            f"Type 'confirm' to proceed or 'edit' to start over."
        )

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
        
        # --- FIXED: Use the stored values, don't overwrite them ---
        # The host and email should already be set from previous steps
        # Only fallback to meeting data if somehow they're missing
        
        if not self.visitor_info.get("host_confirmed"):
            organizer = meeting.get("organizer", {})
            self.visitor_info["host_confirmed"] = (
                organizer.get("displayName") or 
                organizer.get("name") or 
                organizer.get("emailAddress", {}).get("name") or 
                meeting.get("host") or 
                self.visitor_info.get("host_requested") or 
                "N/A"
            )
        
        if not self.visitor_info.get("host_email"):
            organizer = meeting.get("organizer", {})
            self.visitor_info["host_email"] = (
                organizer.get("emailAddress", {}).get("address") or 
                organizer.get("email") or 
                meeting.get("host_email") or 
                "N/A"
            )
        
        if not self.visitor_info.get("visitor_email"):
            attendees = meeting.get("attendees", [])
            if attendees:
                attendee = attendees[0]
                self.visitor_info["visitor_email"] = (
                    attendee.get("emailAddress", {}).get("address") or 
                    attendee.get("email") or 
                    "N/A"
                )
        
        await self.insert_prescheduled_visitor_to_db(
            visitor_type="prescheduled",
            full_name=self.visitor_info["visitor_name"],
            cnic=self.visitor_info["visitor_cnic"],
            phone=self.visitor_info["visitor_phone"],
            host=self.visitor_info["host_confirmed"],
            purpose=meeting.get('subject', ''),
            is_group_visit=False,
            email=self.visitor_info["visitor_email"]
        )
        
        # Notify host via Teams
        access_token = self.ai.get_system_account_token()
        host_user_id = await self.ai.get_user_id(self.visitor_info["host_email"], access_token)
        system_user_id = await self.ai.get_user_id(self.ai._system_account_email, access_token)
        chat_id = await self.ai.create_or_get_chat(host_user_id, system_user_id, access_token)
        message = f"Your scheduled visitor has arrived:\nName: {self.visitor_info['visitor_name']}\nPhone: {self.visitor_info['visitor_phone']}\nEmail: {self.visitor_info['visitor_email']}\nScheduled Time: {meeting.get('start_time', '')}\nPurpose: {meeting.get('subject', '')}"
        await self.ai.send_message_to_host(chat_id, access_token, message)