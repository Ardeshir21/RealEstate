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
            '/mybirthday': self.cmd_set_my_birthday,
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
                {"text": "🎈 Set My Birthday", "callback_data": "set_my_birthday"},
                {"text": "📋 List My Birthdays", "callback_data": "list_birthdays"}
            ],
            [
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
                    new_date_obj = datetime.strptime(message_text.strip(), '%Y-%m-%d').date()
                    
                    birthday.birth_date = new_date_obj
                    birthday.save()
                    
                    # Show success message
                    response = (f"✅ Successfully updated birthday:\n"
                              f"👤 Name: {birthday.name}\n"
                              f"📅 New Gregorian date: {birthday.birth_date}\n"
                              f"🗓️ New Persian date: {birthday.get_persian_date()}\n\n"
                              f"Returning to birthday list...")
                    
                    # Send success message as a new message
                    self.send_message(user_id, response)
                    
                    # After a brief pause, send the birthday list as a new message
                    import time
                    time.sleep(2)
                    response, keyboard = self.get_user_birthdays(user_id)
                    self.send_message(user_id, response, keyboard)
                    
                    # Clear the state after sending messages
                    user_state.delete()
                    
                    return None
                    
                except ValueError:
                    buttons = [[{"text": "🔙 Cancel", "callback_data": "back_to_list"}]]
                    keyboard = self.create_inline_keyboard(buttons)
                    return "❌ Invalid date format. Please use YYYY-MM-DD (e.g., 1990-12-31)", keyboard

            elif user_state.state == "waiting_for_name":
                # Store the name and move to date input
                user_state.context['name'] = message_text.strip()
                user_state.state = 'waiting_for_birthday'
                user_state.save()
                
                buttons = [[{"text": "🔙 Back to Main", "callback_data": "back_to_main"}]]
                keyboard = self.create_inline_keyboard(buttons)
                return ("Please enter the birthday in YYYY-MM-DD format\n"
                       "For example: 1990-12-31"), keyboard

            elif user_state.state == "waiting_for_own_birthday":
                try:
                    birth_date = datetime.strptime(message_text.strip(), '%Y-%m-%d').date()
                    name = user_state.context.get('user_name')
                    
                    # Check for existing birthday with same name and date
                    existing_birthday = GlobalBirthday.objects.filter(
                        name=name,
                        birth_date=birth_date
                    ).first()

                    if existing_birthday:
                        # Update telegram_id if it's not set
                        if not existing_birthday.telegram_id:
                            existing_birthday.telegram_id = user_id
                            existing_birthday.save()
                        
                        # Update user settings
                        UserBirthdaySettings.objects.update_or_create(
                            user_id=user_id,
                            defaults={
                                'user_name': name,
                                'birthday': existing_birthday
                            }
                        )
                        
                        # Clear the state
                        user_state.delete()
                        
                        buttons = [[{"text": "🔙 Back to Main", "callback_data": "back_to_main"}]]
                        keyboard = self.create_inline_keyboard(buttons)
                        return (f"✅ Successfully set your birthday!\n"
                               f"Name: {existing_birthday.name}\n"
                               f"Gregorian: {existing_birthday.birth_date}\n"
                               f"Persian: {existing_birthday.get_persian_date()}\n\n"
                               f"Others will now be able to contact you through the birthday list."), keyboard

                    # Create new birthday entry
                    birthday = GlobalBirthday.objects.create(
                        name=name,
                        birth_date=birth_date,
                        added_by=user_id,
                        telegram_id=user_id  # Always store telegram_id for own birthday
                    )

                    # Create or update user settings
                    UserBirthdaySettings.objects.update_or_create(
                        user_id=user_id,
                        defaults={
                            'user_name': name,
                            'birthday': birthday
                        }
                    )

                    # Clear the state
                    user_state.delete()

                    buttons = [[{"text": "🔙 Back to Main", "callback_data": "back_to_main"}]]
                    keyboard = self.create_inline_keyboard(buttons)
                    return (f"✅ Successfully set your birthday!\n"
                           f"Name: {birthday.name}\n"
                           f"Gregorian: {birthday.birth_date}\n"
                           f"Persian: {birthday.get_persian_date()}\n\n"
                           f"Others will now be able to contact you through the birthday list."), keyboard

                except ValueError:
                    buttons = [[{"text": "🔙 Back to Main", "callback_data": "back_to_main"}]]
                    keyboard = self.create_inline_keyboard(buttons)
                    return "❌ Invalid date format. Please use YYYY-MM-DD (e.g., 1990-12-31)", keyboard

            elif user_state.state == "waiting_for_birthday":
                try:
                    name = user_state.context.get('name')
                    birth_date = datetime.strptime(message_text.strip(), '%Y-%m-%d').date()
                    
                    # Check for existing birthday with same name and date
                    existing_birthday = GlobalBirthday.objects.filter(
                        name=name,
                        birth_date=birth_date
                    ).first()

                    if existing_birthday:
                        # Store context for confirmation
                        user_state.context.update({
                            'birth_date': birth_date.isoformat(),
                            'existing_id': existing_birthday.id
                        })
                        user_state.state = 'confirm_existing'
                        user_state.save()

                        buttons = [
                            [
                                {"text": "✅ Yes, Use Existing", "callback_data": "confirm_existing_yes"},
                                {"text": "❌ No, Create New", "callback_data": "confirm_existing_no"}
                            ],
                            [{"text": "🔙 Back to Main", "callback_data": "back_to_main"}]
                        ]
                        keyboard = self.create_inline_keyboard(buttons)
                        return (f"We found an existing entry:\n"
                               f"Name: {existing_birthday.name}\n"
                               f"Date: {existing_birthday.birth_date}\n"
                               f"Added by: <hidden>\n\n"
                               f"Would you like to use this existing entry?"), keyboard

                    # Create new birthday entry
                    birthday = GlobalBirthday.objects.create(
                        name=name,
                        birth_date=birth_date,
                        added_by=user_id
                    )

                    # Clear the state
                    user_state.delete()

                    buttons = [[{"text": "🔙 Back to Main", "callback_data": "back_to_main"}]]
                    keyboard = self.create_inline_keyboard(buttons)
                    return (f"✅ Birthday successfully added:\n"
                           f"Name: {birthday.name}\n"
                           f"Gregorian: {birthday.birth_date}\n"
                           f"Persian: {birthday.get_persian_date()}"), keyboard

                except ValueError:
                    buttons = [[{"text": "🔙 Back to Main", "callback_data": "back_to_main"}]]
                    keyboard = self.create_inline_keyboard(buttons)
                    return "❌ Invalid date format. Please use YYYY-MM-DD (e.g., 1990-12-31)", keyboard

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

                    buttons = [[{"text": "🔙 Back to Main", "callback_data": "back_to_main"}]]
                    keyboard = self.create_inline_keyboard(buttons)
                    return f"✅ You will be notified {days} days before each birthday", keyboard

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
                              f"🗓️ Persian date: {birthday.get_persian_date()}\n\n"
                              f"Returning to birthday list...")
                    
                    # Send success message as a new message
                    self.send_message(user_id, response)
                    
                    # After a brief pause, send the birthday list as a new message
                    import time
                    time.sleep(2)
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
                    time.sleep(2)
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
                          f"🗓️ Persian date: {birthday.get_persian_date()}\n\n"
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
                          f"Enter -1 to use the default reminder setting ({settings.reminder_days} days)")
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
                
                response = (f"Birthday Details:\n"
                          f"👤 Name: {birthday.name}\n"
                          f"📅 Gregorian: {birthday.birth_date}\n"
                          f"🗓️ Persian: {birthday.get_persian_date()}\n"
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
                          f"🗓️ Current Persian date: {birthday.get_persian_date()}\n\n"
                          f"Please enter the new date in YYYY-MM-DD format:")
                
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
                          f"🗓️ Persian: {birthday.get_persian_date()}")
                
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
                    time.sleep(2)
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

            elif callback_data == "set_my_birthday":
                # Set state for birthday input
                UserState.objects.update_or_create(
                    user_id=user_id,
                    defaults={
                        'state': 'waiting_for_own_birthday',
                        'context': {'user_name': user_name}
                    }
                )
                buttons = [[{"text": "🔙 Back to Main", "callback_data": "back_to_main"}]]
                keyboard = self.create_inline_keyboard(buttons)
                response = ("Please enter your birthday in YYYY-MM-DD format\n"
                          "For example: 1990-12-31")
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
               "• Add birthdays to the global list\n"
               "• Set reminder preferences\n"
               "• View your birthday info\n"
               "• List all birthdays\n"
               "• Manage birthday visibility\n"
               "• Get help\n\n"
               "You can also use /cancel at any time to cancel the current operation.")

    def cmd_set_my_birthday(self, message_text: str, user_id: str, user_name: str) -> str:
        """Handle the command for setting user's own birthday."""
        # Set state for birthday input
        UserState.objects.update_or_create(
            user_id=user_id,
            defaults={
                'state': 'waiting_for_own_birthday',
                'context': {'user_name': user_name}
            }
        )
        
        return ("Please enter your birthday in YYYY-MM-DD format\n"
               "For example: 1990-12-31\n\n"
               "Click Cancel to go back to main menu.")

    def cmd_list_birthdays(self, message_text: str, user_id: str, *args) -> str:
        # Get only birthdays added by the current user
        birthdays = GlobalBirthday.objects.filter(added_by=user_id).order_by('name')  # Sort by name
        settings, _ = UserBirthdaySettings.objects.get_or_create(
            user_id=user_id,
            defaults={'user_name': args[0] if args else "", 'reminder_days': 1}
        )

        if not birthdays:
            return "You haven't added any birthdays yet!"

        today = timezone.now().date()
        response = "🎂 Your Birthdays:\n\n"
        
        for birthday in birthdays:
            next_birthday = birthday.get_next_birthday()
            days_until = (next_birthday - today).days
            persian_date = birthday.get_persian_date()
            reminder_days = birthday.reminder_days if birthday.reminder_days is not None else settings.reminder_days
            
            response += (f"👤 {birthday.name}\n"
                        f"📅 Gregorian: {birthday.birth_date}\n"
                        f"📅 Persian: {persian_date}\n"
                        f"⏳ Days until birthday: {days_until}\n"
                        f"⏰ Reminder: {reminder_days} days before\n")
            
            # Add contact info if it's their own birthday
            if birthday.telegram_id == user_id:
                response += "📱 This is your birthday entry\n"
            
            response += "\n"
        
        return response

    def get_user_birthdays(self, user_id: str, for_edit: bool = False, for_delete: bool = False) -> tuple:
        """Get list of birthdays added by the user with interactive buttons."""
        birthdays = GlobalBirthday.objects.filter(added_by=user_id).order_by('name')  # Sort by name
        
        if not birthdays:
            return "You haven't added any birthdays yet!", self.get_main_menu_keyboard(show_cancel=False)
        
        response = "🎂 Your Birthdays:\n\n"
        
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
                   f"New Persian date: {birthday.get_persian_date()}")
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
        return ("Welcome to Birthday Reminder Bot! 🎉\n\n"
               "Use the buttons below to:\n"
               "• Add birthdays to your private list\n"
               "• Set reminder preferences\n"
               "• Set your own birthday\n"
               "• List your birthdays\n"
               "• Edit or delete your birthdays\n"
               "• Get help\n\n"
               "Available commands:\n"
               "/mybirthday - Set your own birthday\n"
               "/cancel - Cancel current operation\n\n"
               "Features:\n"
               "• Private birthday list for each user\n"
               "• Persian calendar support\n"
               "• Customizable reminders\n"
               "• Edit/delete control over your birthdays")