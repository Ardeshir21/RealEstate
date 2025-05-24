from datetime import datetime
from django.conf import settings
from django.utils import timezone
from typing import Optional, Dict, Any
import logging
import jdatetime
import re
from django.db import IntegrityError

from ..models import GlobalBirthday, UserBirthdaySettings, UserState
from .base import TelegramBot

logger = logging.getLogger(__name__)

class BirthdayBot(TelegramBot):
    def __init__(self):
        token = settings.TELEGRAM_BIRTHDAY_BOT_TOKEN
        super().__init__(token)
        self.commands = {
            '/start': self.cmd_start,
            '/cancel': self.cmd_cancel,
            '/listbirthdays': self.cmd_list_birthdays,
            '/help': self.cmd_help
        }

    def get_main_menu_keyboard(self, show_cancel: bool = False) -> Dict:
        """Create the main menu keyboard."""
        buttons = [
            [
                {"text": "🎂 Add Birthday", "callback_data": "add_birthday"},
                {"text": "⏰ Set Reminder", "callback_data": "set_reminder"}
            ],
            [
                {"text": "📋 Birthdays List", "callback_data": "list_birthdays"},
                {"text": "✏️ Manage My Entries", "callback_data": "manage_entries"}
            ],
            [
                {"text": "❓ Help", "callback_data": "help"}
            ]
        ]
        
        if show_cancel:
            buttons.append([{"text": "❌ Cancel", "callback_data": "cancel"}])
            
        return self.create_inline_keyboard(buttons)

    def get_manage_entries_keyboard(self) -> Dict:
        """Create the manage entries keyboard."""
        buttons = [
            [
                {"text": "✏️ Edit Name", "callback_data": "edit_name"},
                {"text": "📅 Edit Date", "callback_data": "edit_date"}
            ],
            [
                {"text": "🗑️ Delete Birthday", "callback_data": "delete_birthday"}
            ],
            [
                {"text": "🔙 Back to Main", "callback_data": "back_to_main"}
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
            # Get message_id from reply_to_message if it exists, otherwise from the message itself
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
                        # Try to create birthday with the given date string
                        birthday = GlobalBirthday(
                            name=name,
                            birth_date=date_str,  # This will be parsed in save()
                            added_by=user_id
                        )
                        birthday.save()
                        
                        # Clear the state
                        user_state.delete()

                        buttons = [[{"text": "🔙 Back to Main", "callback_data": "back_to_main"}]]
                        keyboard = self.create_inline_keyboard(buttons)
                        return (f"✅ Birthday successfully added:\n"
                               f"Name: {birthday.name}\n"
                               f"📅 Gregorian: {birthday.birth_date}\n"
                               f"🗓️ Persian: {birthday.persian_birth_date}"), keyboard

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

            # Handle edit_name callbacks
            if callback_data.startswith("edit_name_"):
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
                
                response = (f"Birthday Details:\n"
                          f"👤 Name: {birthday.name}\n"
                          f"📅 Gregorian: {birthday.birth_date}\n"
                          f"🗓️ Persian: {birthday.persian_birth_date}\n"
                          f"{zodiac_sign}\n"
                          f"⏰ Reminder: {current_reminder} days before\n\n"
                          f"Choose an action:")
                
                buttons = [
                    [
                        {"text": "✏️ Edit Name", "callback_data": f"edit_name_{birthday_id}"},
                        {"text": "📅 Edit Date", "callback_data": f"edit_prompt_{birthday_id}"}
                    ],
                    [
                        {"text": "⏰ Edit Reminder", "callback_data": f"edit_reminder_{birthday_id}"},
                        {"text": "❌ Delete", "callback_data": f"delete_prompt_{birthday_id}"}
                    ],
                    [{"text": "🔙 Back to List", "callback_data": "back_to_list"}]
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
                
                response = (f"Current birthday info:\n"
                          f"👤 Name: {birthday.name}\n"
                          f"📅 Current date: {birthday.birth_date}\n"
                          f"🗓️ Current Persian date: {birthday.persian_birth_date}\n\n"
                          f"Please enter the new date in one of these formats:\n"
                          f"📅 Gregorian: YYYY-MM-DD (e.g., 1990-12-31)\n"
                          f"🗓️ Persian: YYYY/MM/DD (e.g., 1369/10/10):")
                
                buttons = [[{"text": "🔙 Cancel", "callback_data": "back_to_list"}]]
                keyboard = self.create_inline_keyboard(buttons)
                
                self.answer_callback_query(callback_query_id)
                self.edit_message(user_id, message_id, response, keyboard)
                return

            elif callback_data.startswith("delete_prompt_"):
                birthday_id = int(callback_data.split("_")[-1])
                birthday = GlobalBirthday.objects.get(id=birthday_id)
                
                response = (f"Are you sure you want to delete this birthday?\n\n"
                          f"👤 Name: {birthday.name}\n"
                          f"📅 Date: {birthday.birth_date}\n"
                          f"🗓️ Persian: {birthday.persian_birth_date}")
                
                buttons = [
                    [
                        {"text": "✅ Yes, Delete", "callback_data": f"confirm_delete_{birthday_id}"},
                        {"text": "❌ No, Cancel", "callback_data": "back_to_list"}
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
                response, keyboard = self.get_user_birthdays(user_id)
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

            elif callback_data == "list_birthdays":
                response = self.cmd_list_birthdays("", user_id, user_name)
                buttons = [[{"text": "🔙 Back to Main", "callback_data": "back_to_main"}]]
                keyboard = self.create_inline_keyboard(buttons)
                self.answer_callback_query(callback_query_id)
                self.edit_message(user_id, message_id, response, keyboard)
                return

            elif callback_data == "manage_entries":
                response, keyboard = self.get_user_birthdays(user_id)
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
               "• List all birthdays\n"
               "• Manage your entries\n"
               "• Get help\n\n"
               "You can also use /cancel at any time to cancel the current operation.")

    def cmd_list_birthdays(self, message_text: str, user_id: str, *args) -> str:
        # Get only birthdays added by the current user
        birthdays = GlobalBirthday.objects.filter(added_by=user_id)
        settings, _ = UserBirthdaySettings.objects.get_or_create(
            user_id=user_id,
            defaults={'user_name': args[0] if args else "", 'reminder_days': 1}
        )

        if not birthdays:
            return "You haven't added any birthdays yet!"

        today = timezone.now().date()
        
        # Create a list of birthdays with their next occurrence and days until
        birthday_list = []
        for birthday in birthdays:
            next_birthday = birthday.get_next_birthday()
            days_until = (next_birthday - today).days
            birthday_list.append((birthday, days_until))
        
        # Sort by days until next birthday
        birthday_list.sort(key=lambda x: x[1])
        
        response = "Upcoming Birthdays 🎂\n" + "─" * 30 + "\n\n"
        
        for birthday, days_until in birthday_list:
            persian_date = birthday.persian_birth_date
            reminder_days = birthday.reminder_days if birthday.reminder_days is not None else settings.reminder_days
            zodiac_sign = self.get_zodiac_sign(birthday.birth_date)
            
            # Add emoji indicators for very close birthdays
            days_indicator = "🔔 TODAY!" if days_until == 0 else (
                           "🎉 Tomorrow!" if days_until == 1 else (
                           "⚡️ In 2 days!" if days_until == 2 else (
                           "📅 In 3 days!" if days_until == 3 else
                           f"⏳ In {days_until} days")))

            # Add sparkles for birthdays happening today or tomorrow
            name_decoration = "✨ " if days_until <= 1 else ""
            
            response += f"┌{'─' * 28}\n"
            response += f"│ {name_decoration}{birthday.name} {name_decoration}\n"
            response += f"├{'─' * 28}\n"
            response += f" {days_indicator}\n"
            response += f" 📅 {birthday.birth_date} (Gregorian)\n"
            response += f" 🗓️ {persian_date} (Persian)\n"
            response += f" {zodiac_sign}\n"
            response += f" 🔔 Reminder: {reminder_days} days before\n"
            response += f"└{'─' * 28}\n\n"
        
        return response

    def get_user_birthdays(self, user_id: str, for_edit: bool = False, for_delete: bool = False) -> tuple:
        """Get list of birthdays added by the user with interactive buttons."""
        # Keep alphabetical sorting for editing interface
        birthdays = GlobalBirthday.objects.filter(added_by=user_id).order_by('name')
        
        if not birthdays:
            return "You haven't added any birthdays yet!", self.get_main_menu_keyboard(show_cancel=False)
        
        response = "🎂 Your Birthdays 🎂\n" + "─" * 30 + "\n\n"
        
        buttons = []
        for birthday in birthdays:
            button_text = (f"🎂 {birthday.name} ({birthday.birth_date})")
            # Each birthday gets its own row with a manage option
            buttons.append([{
                "text": button_text,
                "callback_data": f"manage_id_{birthday.id}"
            }])
        
        # Add Back button at the bottom
        buttons.append([{"text": "🔙 Back to Main", "callback_data": "back_to_main"}])
        
        keyboard = self.create_inline_keyboard(buttons)
        return response, keyboard

    def handle_birthday_edit(self, birthday_id: int, user_id: str, new_date: str) -> str:
        """Handle editing a birthday date."""
        try:
            birthday = GlobalBirthday.objects.get(id=birthday_id, added_by=user_id)
            new_date_obj = datetime.strptime(new_date.strip(), '%Y-%m-%d').date()
            
            birthday.birth_date = new_date_obj
            birthday.save()
            
            return (f"✅ Successfully updated birthday:\n"
                   f"Name: {birthday.name}\n"
                   f"New Gregorian date: {birthday.birth_date}\n"
                   f"New Persian date: {birthday.persian_birth_date}")
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

    def cmd_help(self, *args) -> str:
        return ("🎉 Welcome to the Birthday Celebration Central! 🎂\n\n"
               "Never miss a chance to celebrate!"
               "Remember: You can always say /cancel if you need a fresh start. 🔄\n\n"
               "Now, let's make sure no birthday goes uncelebrated! 🎁")

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