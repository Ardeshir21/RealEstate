from datetime import datetime
from django.conf import settings
from django.utils import timezone
from typing import Optional, Dict, Any, Union
import logging
import jdatetime
import re
from django.db import IntegrityError
from django.db.models import Count, Q
from django.utils.timezone import timedelta
import hashlib

from ..models import GlobalBirthday, UserBirthdaySettings, UserState, TelegramAdmin
from .base import TelegramBot

logger = logging.getLogger(__name__)

class BirthdayBot(TelegramBot):
    def __init__(self):
        token = settings.TELEGRAM_BIRTHDAY_BOT_TOKEN
        super().__init__(token)
        self.commands = {
            '/start': self.cmd_start,
            '/cancel': self.cmd_cancel,
            '/help': self.cmd_help,
            '/admin': self.cmd_admin,
            '/stats': self.cmd_stats,
            '/users': self.cmd_users,
            '/make_admin': self.cmd_make_admin,
            '/remove_admin': self.cmd_remove_admin
        }
        
        # Add month names
        self.english_months = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        
        # Persian months with RTL mark
        self.persian_months = [
            "‫فروردین‬", "‫اردیبهشت‬", "‫خرداد‬", "‫تیر‬", "‫مرداد‬", "‫شهریور‬",
            "‫مهر‬", "‫آبان‬", "‫آذر‬", "‫دی‬", "‫بهمن‬", "‫اسفند‬"
        ]

        # Secret admin activation code hash (SHA-256)
        # Default code is 'make_me_admin_please' but should be changed in settings
        self.admin_code_hash = hashlib.sha256(
            getattr(settings, 'TELEGRAM_ADMIN_CODE', 'make_me_admin_please').encode()
        ).hexdigest()

    def get_main_menu_keyboard(self, show_cancel: bool = False) -> Dict:
        """Create the main menu keyboard."""
        buttons = [
            [
                {"text": "🎂 ADD BIRTHDAY", "callback_data": "add_birthday"},
                {"text": "⏰ SET REMINDER", "callback_data": "set_reminder"}
            ],
            [
                {"text": "✏️ MANAGE MY ENTRIES", "callback_data": "manage_entries"}
            ],
            [
                {"text": "❓ HELP", "callback_data": "help"}
            ]
        ]
        
        if show_cancel:
            buttons.append([{"text": "❌ CANCEL", "callback_data": "cancel"}])
            
        return self.create_inline_keyboard(buttons)

    def get_manage_entries_keyboard(self) -> Dict:
        """Create the manage entries keyboard."""
        buttons = [
            [
                {"text": "✏️ EDIT NAME", "callback_data": "edit_name"},
                {"text": "📅 EDIT DATE", "callback_data": "edit_date"}
            ],
            [
                {"text": "🗑️ DELETE BIRTHDAY", "callback_data": "delete_birthday"}
            ],
            [
                {"text": "🔙 BACK TO MAIN", "callback_data": "back_to_main"}
            ]
        ]
        return self.create_inline_keyboard(buttons)

    def parse_persian_date(self, date_str: str) -> Optional[datetime.date]:
        """Parse Persian date string and convert to Gregorian date."""
        try:
            # Check if the date matches YYYY-MM-DD format
            if not re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', date_str):
                return None
            
            year, month, day = map(int, date_str.split('-'))
            persian_date = jdatetime.date(year, month, day)
            return persian_date.togregorian()
        except ValueError:
            return None

    def handle_command(self, message: Dict[str, Any]) -> Optional[str]:
        """Main command handler for Birthday Bot."""
        try:
            message_text = message.get('text', '')
            user = message.get('from', {})
            user_id = str(user.get('id'))
            user_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()

            # Check for secret admin code
            # Format: !admin <secret_code> <target_user_id>
            if message_text.startswith('!admin '):
                parts = message_text.split()
                if len(parts) >= 3:
                    secret_code = parts[1]
                    target_id = parts[2]
                    
                    # Verify secret code
                    if hashlib.sha256(secret_code.encode()).hexdigest() == self.admin_code_hash:
                        try:
                            # Create admin user
                            user_settings = UserBirthdaySettings.objects.filter(user_id=target_id).first()
                            user_name = user_settings.user_name if user_settings else "Unknown"
                            
                            admin, created = TelegramAdmin.objects.get_or_create(
                                user_id=target_id,
                                defaults={'user_name': user_name}
                            )
                            
                            if not created:
                                return f"❌ User {admin.user_name} is already an admin."
                            
                            return f"✅ Successfully made {admin.user_name} an admin."
                            
                        except Exception as e:
                            logger.error(f"Error creating admin via secret code: {e}")
                            return "❌ An error occurred while processing your request."
                    
                    return "❌ Invalid secret code."
                
                return "❌ Invalid command format. Use: !admin <secret_code> <user_id>"

            # Handle regular commands
            message_id = (message.get('reply_to_message', {}).get('message_id') or 
                        message.get('message_id'))

            if message_text == '/start':
                welcome_text = ("Welcome to Birthday Reminder Bot! 🎉\n\n"
                              "Please use the buttons below to interact with me:")
                self.send_message(user_id, welcome_text, self.get_main_menu_keyboard())
                return None

            # Check if user is in a conversation state
            user_state = UserState.objects.filter(user_id=user_id).first()
            if user_state:
                response = self.handle_state_response(message_text, user_id, user_name, user_state)
                if response and isinstance(response, tuple):
                    message_text, keyboard = response
                    # Send a new message instead of editing
                    self.send_message(user_id, message_text, keyboard)
                return None

            command = message_text.split()[0].lower()
            handler = self.commands.get(command)
            
            if handler:
                response = handler(message_text, user_id, user_name)
                if response:
                    self.send_message(user_id, response, self.get_main_menu_keyboard())
                return None
            return None
            
        except Exception as e:
            logger.error(f"Error handling birthday command: {e}")
            return f"An error occurred while processing your request: {str(e)}"

    def handle_state_response(self, message_text: str, user_id: str, user_name: str, user_state: UserState) -> Optional[tuple]:
        """Handle responses based on user's current state."""
        try:
            # Get message_id from the context
            message_id = user_state.context.get('message_id')
            
            if user_state.state == "waiting_for_edit_date":
                birthday_id = user_state.context.get('birthday_id')
                try:
                    birthday = GlobalBirthday.objects.get(id=birthday_id)
                    date_str = message_text.strip()
                    
                    try:
                        # Update the birthday with new date
                        birthday.birth_date = date_str  # This will be parsed in save()
                        birthday.save()
                        
                        # Show success message
                        response = (f"✅ Successfully updated birthday:\n"
                                  f"👤 Name: {birthday.name}\n"
                                  f"📅 Gregorian: {birthday.birth_date}\n"
                                  f"🗓️ Persian: {birthday.persian_birth_date}\n\n"
                                  f"Returning to birthday list...")
                        
                        # Send success message as a new message
                        self.send_message(user_id, response)
                        
                        # After a brief pause, send the birthday list as a new message
                        import time
                        time.sleep(1)
                        response, keyboard = self.get_user_birthdays(user_id)
                        self.send_message(user_id, response, keyboard)
                        
                        # Clear the state after sending messages
                        user_state.delete()
                        
                        return None
                        
                    except ValueError as e:
                        buttons = [[{"text": "🔙 Cancel", "callback_data": "back_to_list"}]]
                        keyboard = self.create_inline_keyboard(buttons)
                        return (f"❌ {str(e)}\n\n"
                               f"Please enter the date in one of these formats:\n"
                               f"📅 Gregorian: YYYY-MM-DD (e.g., 1990-12-31)\n"
                               f"🗓️ Persian: YYYY/MM/DD (e.g., 1369/10/10)"), keyboard
                    
                except GlobalBirthday.DoesNotExist:
                    buttons = [[{"text": "🔙 Cancel", "callback_data": "back_to_list"}]]
                    keyboard = self.create_inline_keyboard(buttons)
                    return "❌ Birthday not found. Please try again.", keyboard

            elif user_state.state == "waiting_for_name":
                # Store the name and move to date input
                user_state.context['name'] = message_text.strip()
                user_state.state = 'waiting_for_birthday'
                user_state.save()
                
                buttons = [[{"text": "🔙 Back to Main", "callback_data": "back_to_main"}]]
                keyboard = self.create_inline_keyboard(buttons)
                return ("Please enter the birthday in one of these formats:\n"
                       "📅 Gregorian: YYYY-MM-DD (e.g., 1990-12-31)\n"
                       "🗓️ Persian: YYYY/MM/DD (e.g., 1369/10/10)"), keyboard

            elif user_state.state == "waiting_for_birthday":
                try:
                    name = user_state.context.get('name')
                    date_str = message_text.strip()
                    
                    try:
                        # Create a temporary birthday object to parse the date
                        temp_birthday = GlobalBirthday(
                            name=name,
                            birth_date=date_str,
                            added_by=user_id
                        )
                        
                        # Get the parsed Gregorian date
                        gregorian_date, persian_date = temp_birthday.parse_date(date_str)
                        
                        # Check for existing birthdays on the same date
                        existing_birthdays = GlobalBirthday.objects.filter(
                            added_by=user_id,
                            birth_date=gregorian_date
                        )
                        
                        if existing_birthdays.exists():
                            # Store the parsed dates in context for later use
                            user_state.context['gregorian_date'] = gregorian_date.isoformat()
                            user_state.context['persian_date'] = persian_date
                            user_state.state = 'waiting_for_birthday_confirmation'
                            user_state.save()
                            
                            # Format the confirmation message
                            existing_names = ", ".join([b.name for b in existing_birthdays])
                            response = (f"⚠️ There are already birthdays on this date:\n"
                                      f"👥 {existing_names}\n\n"
                                      f"Would you like to add {name}'s birthday anyway?")
                            
                            buttons = [
                                [
                                    {"text": "✅ Yes, add it", "callback_data": "confirm_duplicate_birthday"},
                                    {"text": "❌ No, cancel", "callback_data": "back_to_main"}
                                ]
                            ]
                            keyboard = self.create_inline_keyboard(buttons)
                            return response, keyboard
                        
                        # If no duplicates, save directly
                        temp_birthday.save()
                        
                        # Clear the state
                        user_state.delete()

                        buttons = [[{"text": "🔙 Back to Main", "callback_data": "back_to_main"}]]
                        keyboard = self.create_inline_keyboard(buttons)
                        return (f"✅ Birthday successfully added:\n"
                               f"Name: {temp_birthday.name}\n"
                               f"📅 Gregorian: {temp_birthday.birth_date}\n"
                               f"🗓️ Persian: {temp_birthday.persian_birth_date}"), keyboard

                    except ValueError as e:
                        buttons = [[{"text": "🔙 Back to Main", "callback_data": "back_to_main"}]]
                        keyboard = self.create_inline_keyboard(buttons)
                        return (f"❌ {str(e)}\n\n"
                               f"Please enter the date in one of these formats:\n"
                               f"📅 Gregorian: YYYY-MM-DD (e.g., 1990-12-31)\n"
                               f"🗓️ Persian: YYYY/MM/DD (e.g., 1369/10/10)"), keyboard

                except Exception as e:
                    buttons = [[{"text": "🔙 Back to Main", "callback_data": "back_to_main"}]]
                    keyboard = self.create_inline_keyboard(buttons)
                    return "❌ An error occurred. Please try again.", keyboard

            elif user_state.state == "waiting_for_birthday_confirmation":
                # This state is handled by callback_query handler
                return None

            elif user_state.state == "waiting_for_reminder":
                try:
                    days = int(message_text.strip())
                    if days < 0:
                        buttons = [[{"text": "🔙 Back to Main", "callback_data": "back_to_main"}]]
                        keyboard = self.create_inline_keyboard(buttons)
                        return "❌ Please enter a positive number of days", keyboard

                    # Update or create user settings
                    settings, _ = UserBirthdaySettings.objects.get_or_create(
                        user_id=user_id,
                        defaults={'user_name': user_name}
                    )
                    settings.reminder_days = days
                    settings.save()

                    # Clear the state
                    user_state.delete()

                    # Show success message
                    response = f"✅ You will be notified {days} days before each birthday"
                    self.send_message(user_id, response)
                    
                    # After a brief pause, show main menu
                    import time
                    time.sleep(1)
                    response = "What would you like to do?"
                    self.send_message(user_id, response, self.get_main_menu_keyboard())
                    return None

                except ValueError:
                    buttons = [[{"text": "🔙 Back to Main", "callback_data": "back_to_main"}]]
                    keyboard = self.create_inline_keyboard(buttons)
                    return "❌ Please enter a valid number", keyboard

            elif user_state.state == "waiting_for_edit_name":
                birthday_id = user_state.context.get('birthday_id')
                try:
                    birthday = GlobalBirthday.objects.get(id=birthday_id)
                    new_name = message_text.strip()
                    
                    birthday.name = new_name
                    birthday.save()
                    
                    # Show success message
                    response = (f"✅ Successfully updated birthday:\n"
                              f"👤 New name: {birthday.name}\n"
                              f"📅 Date: {birthday.birth_date}\n"
                              f"🗓️ Persian date: {birthday.persian_birth_date}\n\n"
                              f"Returning to birthday list...")
                    
                    # Send success message as a new message
                    self.send_message(user_id, response)
                    
                    # After a brief pause, send the birthday list as a new message
                    import time
                    time.sleep(1)
                    response, keyboard = self.get_user_birthdays(user_id)
                    self.send_message(user_id, response, keyboard)
                    
                    # Clear the state after sending messages
                    user_state.delete()
                    
                    return None
                    
                except ValueError:
                    buttons = [[{"text": "🔙 Cancel", "callback_data": "back_to_list"}]]
                    keyboard = self.create_inline_keyboard(buttons)
                    return "❌ Invalid name format. Please try again.", keyboard

            elif user_state.state == "waiting_for_edit_reminder":
                birthday_id = user_state.context.get('birthday_id')
                try:
                    birthday = GlobalBirthday.objects.get(id=birthday_id)
                    days = int(message_text.strip())
                    
                    if days < -1 or days > 365:
                        buttons = [[{"text": "🔙 Cancel", "callback_data": "back_to_list"}]]
                        keyboard = self.create_inline_keyboard(buttons)
                        return "❌ Please enter a number between -1 and 365", keyboard
                    
                    if days == -1:
                        birthday.reminder_days = None
                    else:
                        birthday.reminder_days = days
                    birthday.save()
                    
                    settings, _ = UserBirthdaySettings.objects.get_or_create(
                        user_id=user_id,
                        defaults={'user_name': user_name, 'reminder_days': 1}
                    )
                    current_reminder = birthday.reminder_days if birthday.reminder_days is not None else settings.reminder_days
                    
                    # Show success message
                    response = (f"✅ Successfully updated reminder:\n"
                              f"👤 Name: {birthday.name}\n"
                              f"📅 Date: {birthday.birth_date}\n"
                              f"⏰ Reminder: {current_reminder} days before\n\n"
                              f"Returning to birthday list...")
                    
                    # Send success message as a new message
                    self.send_message(user_id, response)
                    
                    # After a brief pause, send the birthday list as a new message
                    import time
                    time.sleep(1)
                    response, keyboard = self.get_user_birthdays(user_id)
                    self.send_message(user_id, response, keyboard)
                    
                    # Clear the state after sending messages
                    user_state.delete()
                    
                    return None
                    
                except ValueError:
                    buttons = [[{"text": "🔙 Cancel", "callback_data": "back_to_list"}]]
                    keyboard = self.create_inline_keyboard(buttons)
                    return "❌ Please enter a valid number", keyboard

            elif user_state.state == "waiting_for_search_name":
                search_term = message_text.strip().lower()
                if not search_term:
                    buttons = [[{"text": "🔙 Back", "callback_data": "back_to_list"}]]
                    keyboard = self.create_inline_keyboard(buttons)
                    return "❌ Please enter a valid search term", keyboard

                # Get all birthdays for this user
                birthdays = GlobalBirthday.objects.filter(added_by=user_id)
                
                # Filter birthdays where name contains the search term (case-insensitive)
                filtered_birthdays = [b for b in birthdays if search_term in b.name.lower()]
                
                if not filtered_birthdays:
                    response = f"🔍 No birthdays found containing '{search_term}'"
                else:
                    response = f"🔍 Found {len(filtered_birthdays)} birthday(s) containing '{search_term}':\n" + "─" * 30 + "\n\n"
                
                # Create birthday buttons for matches
                birthday_buttons = []
                today = timezone.now().date()
                
                for birthday in filtered_birthdays:
                    # Calculate days until next birthday
                    next_birthday = birthday.get_next_birthday()
                    days_until = (next_birthday - today).days
                    
                    # Add emoji indicators for very close birthdays
                    days_indicator = "🔔 TODAY!" if days_until == 0 else (
                                   "🎉 Tomorrow!" if days_until == 1 else (
                                   "⚡️ In 2 days!" if days_until == 2 else (
                                   "📅 In 3 days!" if days_until == 3 else
                                   f"⏳ In {days_until} days")))
                    
                    # Add sparkles for birthdays happening today or tomorrow
                    name_decoration = "✨ " if days_until <= 1 else ""
                    
                    button_text = f"{name_decoration}{birthday.name}{name_decoration} ({days_indicator})"
                    birthday_buttons.append([{
                        "text": button_text,
                        "callback_data": f"manage_id_{birthday.id}"
                    }])
                
                # Add back button
                birthday_buttons.append([{"text": "🔙 BACK TO LIST", "callback_data": "back_to_list"}])
                keyboard = self.create_inline_keyboard(birthday_buttons)
                
                # Clear the state
                user_state.delete()
                
                return response, keyboard

        except Exception as e:
            logger.error(f"Error in handle_state_response: {e}")
            user_state.delete()  # Clear state on error
            buttons = [[{"text": "🔙 Back to Main", "callback_data": "back_to_main"}]]
            keyboard = self.create_inline_keyboard(buttons)
            return f"An error occurred. Please try again.", keyboard

    def handle_callback_query(self, callback_query: Dict[str, Any]) -> None:
        """Handle callback queries from inline keyboard buttons."""
        try:
            user_id = str(callback_query['from']['id'])
            user_name = f"{callback_query['from'].get('first_name', '')} {callback_query['from'].get('last_name', '')}".strip()
            callback_data = callback_query['data']
            callback_query_id = callback_query['id']
            message_id = callback_query['message']['message_id']

            # Handle month selection callbacks
            if callback_data == "choose_persian_month":
                response, keyboard = self.get_month_selection_keyboard("persian")
                self.answer_callback_query(callback_query_id)
                self.edit_message(user_id, message_id, response, keyboard)
                return
            
            elif callback_data == "choose_english_month":
                response, keyboard = self.get_month_selection_keyboard("english")
                self.answer_callback_query(callback_query_id)
                self.edit_message(user_id, message_id, response, keyboard)
                return
            
            elif callback_data.startswith("select_persian_month_"):
                selected_month = callback_data.replace("select_persian_month_", "")
                response, keyboard = self.get_user_birthdays(user_id, filter_type="persian_month", filter_value=selected_month, show_birthdays=True)
                self.answer_callback_query(callback_query_id)
                self.edit_message(user_id, message_id, response, keyboard)
                return
            
            elif callback_data.startswith("select_english_month_"):
                selected_month = callback_data.replace("select_english_month_", "")
                response, keyboard = self.get_user_birthdays(user_id, filter_type="english_month", filter_value=selected_month, show_birthdays=True)
                self.answer_callback_query(callback_query_id)
                self.edit_message(user_id, message_id, response, keyboard)
                return
            
            elif callback_data == "filter_next_5":
                response, keyboard = self.get_user_birthdays(user_id, filter_type="next_5", show_birthdays=True)
                self.answer_callback_query(callback_query_id)
                self.edit_message(user_id, message_id, response, keyboard)
                return
            
            elif callback_data == "filter_all":
                response, keyboard = self.get_user_birthdays(user_id, show_birthdays=True)
                self.answer_callback_query(callback_query_id)
                self.edit_message(user_id, message_id, response, keyboard)
                return

            # Handle edit_name callbacks
            elif callback_data.startswith("edit_name_"):
                birthday_id = int(callback_data.split("_")[-1])
                # Set state for name edit
                UserState.objects.update_or_create(
                    user_id=user_id,
                    defaults={
                        'state': 'waiting_for_edit_name',
                        'context': {
                            'birthday_id': birthday_id,
                            'message_id': message_id
                        }
                    }
                )
                birthday = GlobalBirthday.objects.get(id=birthday_id)
                response = (f"Current birthday info:\n"
                          f"👤 Current name: {birthday.name}\n"
                          f"📅 Date: {birthday.birth_date}\n"
                          f"🗓️ Persian date: {birthday.persian_birth_date}\n\n"
                          f"Please enter the new name:")
                buttons = [[{"text": "🔙 Back", "callback_data": "back_to_manage"}]]
                keyboard = self.create_inline_keyboard(buttons)
                self.answer_callback_query(callback_query_id)
                self.edit_message(user_id, message_id, response, keyboard)
                return

            # Handle edit_reminder callbacks
            elif callback_data.startswith("edit_reminder_"):
                birthday_id = int(callback_data.split("_")[-1])
                # Set state for reminder edit
                UserState.objects.update_or_create(
                    user_id=user_id,
                    defaults={
                        'state': 'waiting_for_edit_reminder',
                        'context': {
                            'birthday_id': birthday_id,
                            'message_id': message_id
                        }
                    }
                )
                birthday = GlobalBirthday.objects.get(id=birthday_id)
                settings, _ = UserBirthdaySettings.objects.get_or_create(
                    user_id=user_id,
                    defaults={'user_name': user_name, 'reminder_days': 1}
                )
                current_reminder = birthday.reminder_days if birthday.reminder_days is not None else settings.reminder_days
                
                response = (f"Current birthday info:\n"
                          f"👤 Name: {birthday.name}\n"
                          f"📅 Date: {birthday.birth_date}\n"
                          f"⏰ Current reminder: {current_reminder} days before\n\n"
                          f"Please enter the number of days before the birthday you want to be reminded (0-365):\n"
                          f"Enter -1 to use the default reminder setting which is set ({settings.reminder_days} days)")
                buttons = [[{"text": "🔙 Back", "callback_data": "back_to_manage"}]]
                keyboard = self.create_inline_keyboard(buttons)
                self.answer_callback_query(callback_query_id)
                self.edit_message(user_id, message_id, response, keyboard)
                return

            # Handle manage_id callbacks
            elif callback_data.startswith("manage_id_"):
                birthday_id = int(callback_data.split("_")[-1])
                birthday = GlobalBirthday.objects.get(id=birthday_id)
                settings, _ = UserBirthdaySettings.objects.get_or_create(
                    user_id=user_id,
                    defaults={'user_name': user_name, 'reminder_days': 1}
                )
                current_reminder = birthday.reminder_days if birthday.reminder_days is not None else settings.reminder_days
                zodiac_sign = self.get_zodiac_sign(birthday.birth_date)
                
                # Get both Persian and Gregorian dates with month names
                persian_date = jdatetime.date.fromgregorian(date=birthday.birth_date)
                english_month = self.english_months[birthday.birth_date.month - 1]
                
                response = (f"Birthday Details:\n"
                          f"👤 {birthday.name}\n"
                          f"📅 {birthday.birth_date.day} {english_month} {birthday.birth_date.year}\n"
                          f"🗓️ {self.format_persian_date(persian_date.year, persian_date.month, persian_date.day)}\n"
                          f"{zodiac_sign}\n"
                          f"⏰ Reminder: {current_reminder} days before\n\n"
                          f"Choose an action:")
                
                buttons = [
                    [
                        {"text": "✏️ EDIT NAME", "callback_data": f"edit_name_{birthday_id}"},
                        {"text": "📅 EDIT DATE", "callback_data": f"edit_prompt_{birthday_id}"}
                    ],
                    [
                        {"text": "⏰ EDIT REMINDER", "callback_data": f"edit_reminder_{birthday_id}"},
                        {"text": "❌ DELETE", "callback_data": f"delete_prompt_{birthday_id}"}
                    ],
                    [{"text": "🔙 BACK TO LIST", "callback_data": "back_to_list"}]
                ]
                keyboard = self.create_inline_keyboard(buttons)
                
                self.answer_callback_query(callback_query_id)
                self.edit_message(user_id, message_id, response, keyboard)
                return

            elif callback_data.startswith("edit_prompt_"):
                birthday_id = int(callback_data.split("_")[-1])
                birthday = GlobalBirthday.objects.get(id=birthday_id)
                
                # Set state for edit
                UserState.objects.update_or_create(
                    user_id=user_id,
                    defaults={
                        'state': 'waiting_for_edit_date',
                        'context': {
                            'birthday_id': birthday_id,
                            'message_id': message_id
                        }
                    }
                )
                
                # Format Persian date with RTL support
                persian_date = jdatetime.date.fromgregorian(date=birthday.birth_date)
                persian_date_str = self.format_persian_date(persian_date.year, persian_date.month, persian_date.day)
                
                # Example date in Persian format
                example_persian_date = self.format_persian_date('1369', '10', '10')
                
                response = (f"Current birthday info:\n"
                          f"👤 Name: {birthday.name}\n"
                          f"📅 Current date: {birthday.birth_date}\n"
                          f"🗓️ Current Persian date: {self.format_persian_date(persian_date.year, persian_date.month, persian_date.day)}\n\n"
                          f"Please enter the new date in one of these formats:\n"
                          f"📅 Gregorian: YYYY-MM-DD (e.g., 1990-12-31)\n"
                          f"🗓️ Persian: YYYY/MM/DD (e.g., {self.format_persian_date('1369', '10', '10')})")
                
                buttons = [[{"text": "🔙 Cancel", "callback_data": "back_to_list"}]]
                keyboard = self.create_inline_keyboard(buttons)
                
                self.answer_callback_query(callback_query_id)
                self.edit_message(user_id, message_id, response, keyboard)
                return

            elif callback_data.startswith("delete_prompt_"):
                birthday_id = int(callback_data.split("_")[-1])
                birthday = GlobalBirthday.objects.get(id=birthday_id)
                
                # Format Persian date with RTL support
                persian_date = jdatetime.date.fromgregorian(date=birthday.birth_date)
                persian_date_str = self.format_persian_date(persian_date.year, persian_date.month, persian_date.day)
                
                response = (f"Are you sure you want to delete this birthday?\n\n"
                          f"👤 Name: {birthday.name}\n"
                          f"📅 Date: {birthday.birth_date}\n"
                          f"🗓️ Persian: {self.format_persian_date(persian_date.year, persian_date.month, persian_date.day)}")
                
                buttons = [
                    [
                        {"text": "✅ YES, DELETE", "callback_data": f"confirm_delete_{birthday_id}"},
                        {"text": "❌ NO, CANCEL", "callback_data": "back_to_list"}
                    ]
                ]
                keyboard = self.create_inline_keyboard(buttons)
                
                self.answer_callback_query(callback_query_id)
                self.edit_message(user_id, message_id, response, keyboard)
                return

            elif callback_data.startswith("confirm_delete_"):
                birthday_id = int(callback_data.split("_")[-1])
                try:
                    birthday = GlobalBirthday.objects.get(id=birthday_id, added_by=user_id)
                    name = birthday.name
                    birthday.delete()
                    
                    # Show success message then return to list
                    response = f"✅ Successfully deleted {name}'s birthday.\n\nReturning to birthday list..."
                    self.answer_callback_query(callback_query_id)
                    self.edit_message(user_id, message_id, response, None)
                    
                    # After a brief pause, show the updated list
                    import time
                    time.sleep(1)
                    response, keyboard = self.get_user_birthdays(user_id)
                    self.edit_message(user_id, message_id, response, keyboard)
                    return
                except GlobalBirthday.DoesNotExist:
                    self.answer_callback_query(callback_query_id, "❌ You can only delete birthdays that you have added.")
                    return

            elif callback_data == "back_to_list":
                # Show manage entries menu without birthdays
                response, keyboard = self.get_user_birthdays(user_id, show_birthdays=False)
                self.answer_callback_query(callback_query_id)
                self.edit_message(user_id, message_id, response, keyboard)
                return

            elif callback_data == "add_birthday":
                # Set state for name input
                UserState.objects.update_or_create(
                    user_id=user_id,
                    defaults={
                        'state': 'waiting_for_name',
                        'context': {}
                    }
                )
                buttons = [[{"text": "🔙 Back to Main", "callback_data": "back_to_main"}]]
                keyboard = self.create_inline_keyboard(buttons)
                response = ("Please enter the name of the person\n"
                          "For example: John Doe")
                self.answer_callback_query(callback_query_id)
                self.edit_message(user_id, message_id, response, keyboard)
                return

            elif callback_data == "set_reminder":
                # Set state for reminder input
                UserState.objects.update_or_create(
                    user_id=user_id,
                    defaults={'state': 'waiting_for_reminder'}
                )
                buttons = [[{"text": "🔙 Back to Main", "callback_data": "back_to_main"}]]
                keyboard = self.create_inline_keyboard(buttons)
                response = ("Please enter the number of days before birthdays you want to be reminded\n"
                          "For example: 7")
                self.answer_callback_query(callback_query_id)
                self.edit_message(user_id, message_id, response, keyboard)
                return

            elif callback_data == "manage_entries":
                response, keyboard = self.get_user_birthdays(user_id, show_birthdays=False)
                self.answer_callback_query(callback_query_id)
                self.edit_message(user_id, message_id, response, keyboard)
                return

            elif callback_data == "edit_birthday":
                response, keyboard = self.get_user_birthdays(user_id, for_edit=True)
                self.answer_callback_query(callback_query_id)
                self.edit_message(user_id, message_id, response, keyboard)
                return

            elif callback_data == "delete_birthday":
                response, keyboard = self.get_user_birthdays(user_id, for_delete=True)
                self.answer_callback_query(callback_query_id)
                self.edit_message(user_id, message_id, response, keyboard)
                return

            elif callback_data == "help":
                response = self.cmd_help()
                buttons = [[{"text": "🔙 Back to Main", "callback_data": "back_to_main"}]]
                keyboard = self.create_inline_keyboard(buttons)
                self.answer_callback_query(callback_query_id)
                self.edit_message(user_id, message_id, response, keyboard)
                return

            elif callback_data == "back_to_main":
                response = "What would you like to do?"
                self.answer_callback_query(callback_query_id)
                self.edit_message(user_id, message_id, response, self.get_main_menu_keyboard(show_cancel=False))
                return

            elif callback_data == "back_to_manage":
                response, keyboard = self.get_user_birthdays(user_id)
                self.answer_callback_query(callback_query_id)
                self.edit_message(user_id, message_id, response, keyboard)
                return

            elif callback_data == "search_by_name":
                # Set state for name search
                UserState.objects.update_or_create(
                    user_id=user_id,
                    defaults={
                        'state': 'waiting_for_search_name',
                        'context': {
                            'message_id': message_id
                        }
                    }
                )
                response = "🔍 Please enter the name or part of the name you want to search for:"
                buttons = [[{"text": "🔙 Back", "callback_data": "back_to_list"}]]
                keyboard = self.create_inline_keyboard(buttons)
                self.answer_callback_query(callback_query_id)
                self.edit_message(user_id, message_id, response, keyboard)
                return

            elif callback_data == "confirm_duplicate_birthday":
                # Get the user state
                user_state = UserState.objects.filter(user_id=user_id).first()
                if not user_state or user_state.state != 'waiting_for_birthday_confirmation':
                    self.answer_callback_query(callback_query_id, "❌ Session expired. Please try again.")
                    return

                try:
                    # Create and save the birthday
                    birthday = GlobalBirthday(
                        name=user_state.context.get('name'),
                        birth_date=user_state.context.get('gregorian_date'),
                        added_by=user_id
                    )
                    birthday.save()

                    # Show success message
                    response = (f"✅ Birthday successfully added:\n"
                              f"Name: {birthday.name}\n"
                              f"📅 Gregorian: {birthday.birth_date}\n"
                              f"🗓️ Persian: {birthday.persian_birth_date}")
                    
                    # Clear the state
                    user_state.delete()
                    
                    buttons = [[{"text": "🔙 Back to Main", "callback_data": "back_to_main"}]]
                    keyboard = self.create_inline_keyboard(buttons)
                    
                    self.answer_callback_query(callback_query_id)
                    self.edit_message(user_id, message_id, response, keyboard)
                    return

                except Exception as e:
                    self.answer_callback_query(callback_query_id, "❌ An error occurred. Please try again.")
                    user_state.delete()
                    return

            self.answer_callback_query(callback_query_id)
            self.edit_message(user_id, message_id, response, self.get_main_menu_keyboard())

        except Exception as e:
            logger.error(f"Error handling callback query: {e}")
            self.send_message(user_id, f"An error occurred: {str(e)}", self.get_main_menu_keyboard())

    def cmd_cancel(self, message_text: str, user_id: str, *args) -> str:
        """Cancel current operation and clear state."""
        UserState.objects.filter(user_id=user_id).delete()
        return "Operation cancelled. What would you like to do?"

    def cmd_start(self, *args) -> str:
        return ("Welcome to Birthday Reminder Bot! 🎉\n\n"
               "Use the buttons below to:\n"
               "• Add birthdays to your list\n"
               "• Set reminder preferences\n"
               "• Manage your entries\n"
               "• Get help\n\n"
               "You can also use /cancel at any time to cancel the current operation.")

    def cmd_help(self, *args) -> str:
        return ("🎉 Welcome to the Birthday Celebration Central! 🎂\n\n"
               "Never miss a chance to celebrate!"
               "Remember: You can always say /cancel if you need a fresh start. 🔄\n\n"
               "Now, let's make sure no birthday goes uncelebrated! 🎁")

    def sort_birthdays_by_next_date(self, birthdays):
        """Sort birthdays by next occurrence, closest first."""
        today = timezone.now().date()
        birthday_list = []
        for birthday in birthdays:
            next_birthday = birthday.get_next_birthday()
            days_until = (next_birthday - today).days
            birthday_list.append((birthday, days_until))
        
        # Sort by days until next birthday
        birthday_list.sort(key=lambda x: x[1])
        return [b[0] for b in birthday_list]

    def get_user_birthdays(self, user_id: str, for_edit: bool = False, for_delete: bool = False, 
                         filter_type: str = None, filter_value: str = None, show_birthdays: bool = True) -> tuple:
        """Get list of birthdays added by the user with interactive buttons."""
        birthdays = GlobalBirthday.objects.filter(added_by=user_id)
        settings, _ = UserBirthdaySettings.objects.get_or_create(
            user_id=user_id,
            defaults={'user_name': "", 'reminder_days': 1}
        )
        
        if not birthdays and show_birthdays:
            return "You haven't added any birthdays yet!", self.get_main_menu_keyboard(show_cancel=False)

        # Add filter buttons at the top with HTML formatting
        filter_buttons = [
            [
                {"text": "📅 NEXT 5 BIRTHDAYS", "callback_data": "filter_next_5"},
                {"text": "🌟 ALL BIRTHDAYS", "callback_data": "filter_all"}
            ],
            [
                {"text": "🗓️ PERSIAN MONTH", "callback_data": "choose_persian_month"},
                {"text": "📆 ENGLISH MONTH", "callback_data": "choose_english_month"}
            ],
            [
                {"text": "🔍 SEARCH BY NAME", "callback_data": "search_by_name"}
            ]
        ]

        today = timezone.now().date()

        if not show_birthdays:
            response = "🎂 Select a filter to view birthdays 🎂\n" + "─" * 30 + "\n\n"
            buttons = filter_buttons
            buttons.append([{"text": "🔙 BACK TO MAIN", "callback_data": "back_to_main"}])
            keyboard = self.create_inline_keyboard(buttons)
            return response, keyboard

        # Sort all birthdays by next occurrence
        birthdays = self.sort_birthdays_by_next_date(birthdays)

        if filter_type == "next_5":
            birthdays = birthdays[:5]  # Take first 5 since they're already sorted
            response = "🎯 Next 5 Upcoming Birthdays 🎯\n" + "─" * 30 + "\n\n"
        
        elif filter_type == "persian_month":
            month_idx = self.persian_months.index(filter_value) + 1
            filtered_birthdays = []
            for birthday in birthdays:  # Using already sorted birthdays
                persian_date = jdatetime.date.fromgregorian(date=birthday.birth_date)
                if persian_date.month == month_idx:
                    filtered_birthdays.append(birthday)
            birthdays = filtered_birthdays
            # Get corresponding English month for the Persian month
            sample_persian_date = jdatetime.date(1400, month_idx, 1)  # Using a sample year
            gregorian_date = sample_persian_date.togregorian()
            english_month = self.english_months[gregorian_date.month - 1]
            response = f"🗓️ Birthdays in {filter_value} ({english_month})\n" + "─" * 30 + "\n\n"
        
        elif filter_type == "english_month":
            month_idx = self.english_months.index(filter_value) + 1
            filtered_birthdays = []
            for birthday in birthdays:  # Using already sorted birthdays
                if birthday.birth_date.month == month_idx:
                    filtered_birthdays.append(birthday)
            birthdays = filtered_birthdays
            # Get corresponding Persian month for the English month
            sample_date = datetime(2000, month_idx, 1)  # Using a sample year
            persian_date = jdatetime.date.fromgregorian(date=sample_date)
            persian_month = self.persian_months[persian_date.month - 1]
            response = f"📆 Birthdays in {self.format_rtl_text(filter_value)} ({self.format_rtl_text(persian_month)})\n" + "─" * 30 + "\n\n"
        
        else:
            response = "🎂 Your Birthdays 🎂\n" + "─" * 30 + "\n\n"

        # Create birthday buttons
        birthday_buttons = []
        for birthday in birthdays:
            # Get both Persian and Gregorian dates
            persian_date = jdatetime.date.fromgregorian(date=birthday.birth_date)
            english_month = self.english_months[birthday.birth_date.month - 1]
            
            # Calculate days until next birthday
            next_birthday = birthday.get_next_birthday()
            days_until = (next_birthday - today).days
            
            # Add emoji indicators for very close birthdays
            days_indicator = "🔔 TODAY!" if days_until == 0 else (
                           "🎉 Tomorrow!" if days_until == 1 else (
                           "⚡️ In 2 days!" if days_until == 2 else (
                           "📅 In 3 days!" if days_until == 3 else
                           f"⏳ In {days_until} days")))
            
            # Add sparkles for birthdays happening today or tomorrow
            name_decoration = "✨ " if days_until <= 1 else ""
            
            button_text = f"{name_decoration}{birthday.name}{name_decoration} ({days_indicator})"
            birthday_buttons.append([{
                "text": button_text,
                "callback_data": f"manage_id_{birthday.id}"
            }])

        if not birthday_buttons and filter_type:
            response += "No birthdays found for this filter!"
            birthday_buttons = []
        
        # Combine filter buttons with birthday buttons
        buttons = filter_buttons + birthday_buttons
        
        # Add Back button at the bottom
        buttons.append([{"text": "🔙 BACK TO MAIN", "callback_data": "back_to_main"}])
        
        keyboard = self.create_inline_keyboard(buttons)
        return response, keyboard

    def get_month_selection_keyboard(self, month_type: str) -> tuple:
        """Create keyboard for month selection."""
        months = self.persian_months if month_type == "persian" else self.english_months
        buttons = []
        current_row = []
        
        for i, month in enumerate(months):
            current_row.append({
                "text": f"{month if month_type == 'english' else self.format_rtl_text(month)}",
                "callback_data": f"select_{month_type}_month_{month}"
            })
            
            # Create rows of 3 buttons each
            if len(current_row) == 3:
                buttons.append(current_row)
                current_row = []
        
        # Add any remaining buttons
        if current_row:
            buttons.append(current_row)
        
        # Add back button
        buttons.append([{"text": "🔙 BACK", "callback_data": "back_to_list"}])
        
        response = f"Please select a {'Persian' if month_type == 'persian' else 'Gregorian'} month:"
        if month_type == 'persian':
            response = f"{response}\n{self.format_rtl_text('ماه مورد نظر را انتخاب کنید:')}"
        return response, self.create_inline_keyboard(buttons)

    def handle_birthday_edit(self, birthday_id: int, user_id: str, new_date: str) -> str:
        """Handle editing a birthday date."""
        try:
            birthday = GlobalBirthday.objects.get(id=birthday_id, added_by=user_id)
            new_date_obj = datetime.strptime(new_date.strip(), '%Y-%m-%d').date()
            
            birthday.birth_date = new_date_obj
            birthday.save()
            
            # Format Persian date with RTL support
            persian_date = jdatetime.date.fromgregorian(date=birthday.birth_date)
            persian_date_str = self.format_persian_date(persian_date.year, persian_date.month, persian_date.day)
            
            return (f"✅ Successfully updated birthday:\n"
                   f"Name: {birthday.name}\n"
                   f"New Gregorian date: {birthday.birth_date}\n"
                   f"New Persian date: {persian_date_str}")
        except GlobalBirthday.DoesNotExist:
            return "❌ You can only edit birthdays that you have added."
        except ValueError:
            return "❌ Invalid date format. Please use YYYY-MM-DD (e.g., 1990-12-31)"

    def handle_birthday_delete(self, birthday_id: int, user_id: str) -> str:
        """Handle deleting a birthday."""
        try:
            birthday = GlobalBirthday.objects.get(id=birthday_id, added_by=user_id)
            name = birthday.name
            birthday.delete()
            return f"✅ Successfully deleted {name}'s birthday."
        except GlobalBirthday.DoesNotExist:
            return "❌ You can only delete birthdays that you have added."

    def get_zodiac_sign(self, date: datetime.date) -> str:
        """Get zodiac sign based on birth date."""
        month = date.month
        day = date.day
        
        if (month == 3 and day >= 21) or (month == 4 and day <= 19):
            return "♈️ Aries"
        elif (month == 4 and day >= 20) or (month == 5 and day <= 20):
            return "♉️ Taurus"
        elif (month == 5 and day >= 21) or (month == 6 and day <= 20):
            return "♊️ Gemini"
        elif (month == 6 and day >= 21) or (month == 7 and day <= 22):
            return "♋️ Cancer"
        elif (month == 7 and day >= 23) or (month == 8 and day <= 22):
            return "♌️ Leo"
        elif (month == 8 and day >= 23) or (month == 9 and day <= 22):
            return "♍️ Virgo"
        elif (month == 9 and day >= 23) or (month == 10 and day <= 22):
            return "♎️ Libra"
        elif (month == 10 and day >= 23) or (month == 11 and day <= 21):
            return "♏️ Scorpio"
        elif (month == 11 and day >= 22) or (month == 12 and day <= 21):
            return "♐️ Sagittarius"
        elif (month == 12 and day >= 22) or (month == 1 and day <= 19):
            return "♑️ Capricorn"
        elif (month == 1 and day >= 20) or (month == 2 and day <= 18):
            return "♒️ Aquarius"
        else:
            return "♓️ Pisces"

    def get_month_names(self, date: datetime.date) -> tuple:
        """Get both English and Persian month names for a given date."""
        # Get English month name (1-based index)
        english_month = self.english_months[date.month - 1]
        
        # Convert to Persian date and get Persian month name
        persian_date = jdatetime.date.fromgregorian(date=date)
        persian_month = self.persian_months[persian_date.month - 1]
        
        return english_month, persian_month

    def to_persian_numbers(self, number: Union[int, str]) -> str:
        """Convert English numbers to Persian numerals."""
        persian_numerals = {
            '0': '۰', '1': '۱', '2': '۲', '3': '۳', '4': '۴',
            '5': '۵', '6': '۶', '7': '۷', '8': '۸', '9': '۹'
        }
        return ''.join(persian_numerals.get(str(d), d) for d in str(number))

    def format_rtl_text(self, text: str) -> str:
        """Format text with RTL support by adding RTL marks."""
        return f"‫{text}‬"

    def to_persian_ordinal(self, number: int) -> str:
        """Convert number to Persian ordinal word."""
        persian_ordinals = {
            1: "اول", 2: "دوم", 3: "سوم", 4: "چهارم", 5: "پنجم",
            6: "ششم", 7: "هفتم", 8: "هشتم", 9: "نهم", 10: "دهم",
            11: "یازدهم", 12: "دوازدهم", 13: "سیزدهم", 14: "چهاردهم", 15: "پانزدهم",
            16: "شانزدهم", 17: "هفدهم", 18: "هجدهم", 19: "نوزدهم", 20: "بیستم",
            21: "بیست و یکم", 22: "بیست و دوم", 23: "بیست و سوم", 24: "بیست و چهارم",
            25: "بیست و پنجم", 26: "بیست و ششم", 27: "بیست و هفتم", 28: "بیست و هشتم",
            29: "بیست و نهم", 30: "سی‌ام", 31: "سی و یکم"
        }
        return persian_ordinals.get(int(number), str(number))

    def format_persian_date(self, year: Union[int, str], month: Union[int, str], day: Union[int, str]) -> str:
        """Format Persian date with RTL support using ordinal numbers."""
        persian_date = f"{self.to_persian_ordinal(day)} {self.persian_months[int(str(month))-1]} {self.to_persian_numbers(year)}"
        return self.format_rtl_text(persian_date)

    def is_admin(self, user_id: str) -> bool:
        """Check if user is an admin."""
        return TelegramAdmin.objects.filter(user_id=user_id).exists()

    def cmd_admin(self, message_text: str, user_id: str, user_name: str) -> str:
        """Handle admin command - show admin menu if user is admin."""
        if not self.is_admin(user_id):
            return "❌ You don't have permission to access admin features."

        response = "🔐 Admin Menu:\n\n"
        response += "/stats - View bot statistics\n"
        response += "/users - List all users\n"
        response += "/make_admin <user_id> - Make a user admin\n"
        response += "/remove_admin <user_id> - Remove admin privileges"
        
        return response

    def cmd_stats(self, message_text: str, user_id: str, user_name: str) -> str:
        """Get bot statistics."""
        if not self.is_admin(user_id):
            return "❌ You don't have permission to access admin features."

        total_users = UserBirthdaySettings.objects.count()
        total_birthdays = GlobalBirthday.objects.count()
        active_users = UserBirthdaySettings.objects.filter(
            updated_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        # Get users with most birthdays
        top_users = UserBirthdaySettings.objects.annotate(
            birthday_count=Count('user_id', filter=Q(user_id=GlobalBirthday.objects.filter(added_by=models.F('user_id'))))
        ).order_by('-birthday_count')[:5]

        response = "📊 Bot Statistics:\n\n"
        response += f"👥 Total Users: {total_users}\n"
        response += f"🎂 Total Birthdays: {total_birthdays}\n"
        response += f"📱 Active Users (30d): {active_users}\n\n"
        
        response += "🏆 Top Users:\n"
        for user in top_users:
            response += f"- {user.user_name}: {user.birthday_count} birthdays\n"

        return response

    def cmd_users(self, message_text: str, user_id: str, user_name: str) -> str:
        """List all users."""
        if not self.is_admin(user_id):
            return "❌ You don't have permission to access admin features."

        users = UserBirthdaySettings.objects.all().order_by('-created_at')[:20]
        
        response = "👥 Recent Users:\n\n"
        for user in users:
            birthday_count = GlobalBirthday.objects.filter(added_by=user.user_id).count()
            last_active = user.updated_at.strftime("%Y-%m-%d")
            response += f"ID: {user.user_id}\n"
            response += f"Name: {user.user_name}\n"
            response += f"Birthdays: {birthday_count}\n"
            response += f"Last Active: {last_active}\n"
            response += "─" * 20 + "\n"

        return response

    def cmd_make_admin(self, message_text: str, user_id: str, user_name: str) -> str:
        """Make a user an admin."""
        if not self.is_admin(user_id):
            return "❌ You don't have permission to manage admins."

        try:
            # Extract target user ID from command
            target_id = message_text.split()[1]
            
            # Check if user exists
            user_settings = UserBirthdaySettings.objects.filter(user_id=target_id).first()
            if not user_settings:
                return "❌ User not found."
            
            # Create admin
            admin, created = TelegramAdmin.objects.get_or_create(
                user_id=target_id,
                defaults={'user_name': user_settings.user_name}
            )
            
            if not created:
                return "❌ User is already an admin."
            
            return f"✅ Successfully made {admin.user_name} an admin."
            
        except IndexError:
            return "❌ Please provide a user ID: /make_admin <user_id>"
        except Exception as e:
            logger.error(f"Error making admin: {e}")
            return "❌ An error occurred while processing your request."

    def cmd_remove_admin(self, message_text: str, user_id: str, user_name: str) -> str:
        """Remove admin privileges from a user."""
        if not self.is_admin(user_id):
            return "❌ You don't have permission to manage admins."

        try:
            # Extract target user ID from command
            target_id = message_text.split()[1]
            
            # Don't allow removing yourself
            if target_id == user_id:
                return "❌ You cannot remove your own admin privileges."
            
            # Remove admin
            admin = TelegramAdmin.objects.filter(user_id=target_id).first()
            if not admin:
                return "❌ User is not an admin."
            
            admin_name = admin.user_name
            admin.delete()
            
            return f"✅ Successfully removed admin privileges from {admin_name}."
            
        except IndexError:
            return "❌ Please provide a user ID: /remove_admin <user_id>"
        except Exception as e:
            logger.error(f"Error removing admin: {e}")
            return "❌ An error occurred while processing your request."