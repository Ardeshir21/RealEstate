from datetime import datetime
from django.conf import settings
from django.utils import timezone
from typing import Optional, Dict, Any
import logging
import jdatetime
import re
from django.db import IntegrityError

from ..models import GlobalBirthday, UserBirthdaySettings, UserBirthdayExclusion, UserState
from .base import TelegramBot

logger = logging.getLogger(__name__)

class BirthdayBot(TelegramBot):
    def __init__(self):
        token = settings.TELEGRAM_BIRTHDAY_BOT_TOKEN
        super().__init__(token)
        self.commands = {
            '/start': self.cmd_start,
            '/cancel': self.cmd_cancel,
            '/mybirthday': self.cmd_my_birthday,
            '/listbirthdays': self.cmd_list_birthdays,
            '/help': self.cmd_help,
            '/exclude': self.cmd_exclude,
            '/include': self.cmd_include
        }

    def get_main_menu_keyboard(self, show_cancel: bool = True) -> Dict:
        """Create the main menu keyboard."""
        buttons = [
            [
                {"text": "🎂 Add Birthday", "callback_data": "add_birthday"},
                {"text": "⏰ Set Reminder", "callback_data": "set_reminder"}
            ],
            [
                {"text": "🎈 My Birthday Info", "callback_data": "my_birthday"},
                {"text": "📋 List All Birthdays", "callback_data": "list_birthdays"}
            ],
            [
                {"text": "👁️ Manage Visibility", "callback_data": "manage_visibility"},
                {"text": "❓ Help", "callback_data": "help"}
            ]
        ]
        
        if show_cancel:
            buttons.append([{"text": "❌ Cancel", "callback_data": "cancel"}])
            
        return self.create_inline_keyboard(buttons)

    def get_visibility_keyboard(self) -> Dict:
        """Create the visibility management keyboard."""
        buttons = [
            [
                {"text": "🔍 View Excluded", "callback_data": "view_excluded"},
                {"text": "➕ Include Birthday", "callback_data": "include_birthday"}
            ],
            [
                {"text": "➖ Exclude Birthday", "callback_data": "exclude_birthday"},
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

            if message_text == '/start':
                welcome_text = ("Welcome to Birthday Reminder Bot! 🎉\n\n"
                              "Please use the buttons below to interact with me:")
                self.send_message(user_id, welcome_text, self.get_main_menu_keyboard())
                return None

            # Check if user is in a conversation state
            user_state = UserState.objects.filter(user_id=user_id).first()
            if user_state:
                return self.handle_state_response(message_text, user_id, user_name, user_state)

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

    def handle_state_response(self, message_text: str, user_id: str, user_name: str, user_state: UserState) -> Optional[str]:
        """Handle responses based on user's current state."""
        try:
            if user_state.state == "waiting_for_name":
                # Store the name and move to date input
                user_state.context['name'] = message_text.strip()
                user_state.state = 'waiting_for_birthday'
                user_state.save()
                
                return ("Please enter the birthday in YYYY-MM-DD format\n"
                       "For example: 1990-12-31\n\n"
                       "Click Cancel to go back to main menu.")

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

                        return (f"We found an existing entry:\n"
                               f"Name: {existing_birthday.name}\n"
                               f"Date: {existing_birthday.birth_date}\n"
                               f"Added by: <hidden>\n\n"
                               f"Would you like to use this existing entry? (yes/no)")

                    # Create new birthday entry
                    birthday = GlobalBirthday.objects.create(
                        name=name,
                        birth_date=birth_date,
                        added_by=user_id
                    )

                    # Create or update user settings
                    UserBirthdaySettings.objects.update_or_create(
                        user_id=user_id,
                        defaults={
                            'user_name': user_name,
                            'birthday': birthday if name == user_name else None
                        }
                    )

                    # Clear the state
                    user_state.delete()

                    response = (f"✅ Birthday successfully added:\n"
                              f"Name: {birthday.name}\n"
                              f"Gregorian: {birthday.birth_date}\n"
                              f"Persian: {birthday.get_persian_date()}")
                    self.send_message(user_id, response, self.get_main_menu_keyboard(show_cancel=False))
                    return None

                except ValueError:
                    return "❌ Invalid date format. Please use YYYY-MM-DD (e.g., 1990-12-31)\nOr click Cancel to go back to main menu."

            elif user_state.state == "confirm_existing":
                answer = message_text.strip().lower()
                if answer not in ['yes', 'no']:
                    return "Please answer 'yes' or 'no'"

                name = user_state.context.get('name')
                existing_id = user_state.context.get('existing_id')

                if answer == 'yes':
                    # Use existing birthday
                    birthday = GlobalBirthday.objects.get(id=existing_id)
                    
                    # Create or update user settings
                    UserBirthdaySettings.objects.update_or_create(
                        user_id=user_id,
                        defaults={
                            'user_name': user_name,
                            'birthday': birthday if name == user_name else None
                        }
                    )

                    response = (f"✅ Successfully linked to existing birthday:\n"
                              f"Name: {birthday.name}\n"
                              f"Gregorian: {birthday.birth_date}\n"
                              f"Persian: {birthday.get_persian_date()}")

                else:
                    # Create new birthday entry
                    birth_date = datetime.fromisoformat(user_state.context.get('birth_date')).date()
                    birthday = GlobalBirthday.objects.create(
                        name=name,
                        birth_date=birth_date,
                        added_by=user_id
                    )

                    # Create or update user settings
                    UserBirthdaySettings.objects.update_or_create(
                        user_id=user_id,
                        defaults={
                            'user_name': user_name,
                            'birthday': birthday if name == user_name else None
                        }
                    )

                    response = (f"✅ New birthday entry created:\n"
                              f"Name: {birthday.name}\n"
                              f"Gregorian: {birthday.birth_date}\n"
                              f"Persian: {birthday.get_persian_date()}")

                # Clear the state
                user_state.delete()
                self.send_message(user_id, response, self.get_main_menu_keyboard(show_cancel=False))
                return None

            elif user_state.state == "waiting_for_reminder":
                try:
                    days = int(message_text.strip())
                    if days < 0:
                        return "❌ Please enter a positive number of days\nOr click Cancel to go back to main menu."

                    # Update or create user settings
                    settings, _ = UserBirthdaySettings.objects.get_or_create(
                        user_id=user_id,
                        defaults={'user_name': user_name}
                    )
                    settings.reminder_days = days
                    settings.save()

                    # Clear the state
                    user_state.delete()

                    response = f"✅ You will be notified {days} days before each birthday"
                    self.send_message(user_id, response, self.get_main_menu_keyboard(show_cancel=False))
                    return None

                except ValueError:
                    return "❌ Please enter a valid number\nOr click Cancel to go back to main menu."

            elif user_state.state in ["waiting_for_exclude", "waiting_for_include"]:
                try:
                    birthday_id = int(message_text.strip())
                    birthday = GlobalBirthday.objects.get(id=birthday_id)
                    
                    if user_state.state == "waiting_for_exclude":
                        UserBirthdayExclusion.objects.get_or_create(
                            user_id=user_id,
                            birthday=birthday
                        )
                        response = f"✅ {birthday.name}'s birthday has been excluded from your view"
                    else:  # waiting_for_include
                        UserBirthdayExclusion.objects.filter(
                            user_id=user_id,
                            birthday=birthday
                        ).delete()
                        response = f"✅ {birthday.name}'s birthday has been included in your view"

                    # Clear the state
                    user_state.delete()
                    self.send_message(user_id, response, self.get_main_menu_keyboard(show_cancel=False))
                    return None

                except (ValueError, GlobalBirthday.DoesNotExist):
                    return "❌ Invalid birthday ID. Please enter a valid number from the list\nOr click Cancel to go back to main menu."

        except Exception as e:
            logger.error(f"Error in handle_state_response: {e}")
            user_state.delete()  # Clear state on error
            return "An error occurred. Please try again."

    def handle_callback_query(self, callback_query: Dict[str, Any]) -> None:
        """Handle callback queries from inline keyboard buttons."""
        try:
            user_id = str(callback_query['from']['id'])
            user_name = f"{callback_query['from'].get('first_name', '')} {callback_query['from'].get('last_name', '')}".strip()
            callback_data = callback_query['data']
            callback_query_id = callback_query['id']

            if callback_data == "add_birthday":
                # Set state for name input
                UserState.objects.update_or_create(
                    user_id=user_id,
                    defaults={
                        'state': 'waiting_for_name',
                        'context': {}
                    }
                )
                response = ("Please enter the name of the person\n"
                          "For example: John Doe\n\n"
                          "Click Cancel to go back to main menu.")

            elif callback_data == "set_reminder":
                # Set state for reminder input
                UserState.objects.update_or_create(
                    user_id=user_id,
                    defaults={'state': 'waiting_for_reminder'}
                )
                response = ("Please enter the number of days before birthdays you want to be reminded\n"
                          "For example: 7\n\n"
                          "Click Cancel to go back to main menu.")

            elif callback_data == "my_birthday":
                response = self.cmd_my_birthday("", user_id, user_name)
                self.answer_callback_query(callback_query_id)
                self.send_message(user_id, response, self.get_main_menu_keyboard(show_cancel=False))
                return

            elif callback_data == "list_birthdays":
                response = self.cmd_list_birthdays("", user_id, user_name)
                self.answer_callback_query(callback_query_id)
                self.send_message(user_id, response, self.get_main_menu_keyboard(show_cancel=False))
                return

            elif callback_data == "manage_visibility":
                self.answer_callback_query(callback_query_id)
                self.send_message(user_id, "Birthday Visibility Management:", self.get_visibility_keyboard())
                return

            elif callback_data == "view_excluded":
                response, keyboard = self.get_excluded_birthdays(user_id)
                self.answer_callback_query(callback_query_id)
                self.send_message(user_id, response, keyboard)
                return

            elif callback_data.startswith("exclude_id_"):
                birthday_id = int(callback_data.split("_")[-1])
                birthday = GlobalBirthday.objects.get(id=birthday_id)
                UserBirthdayExclusion.objects.get_or_create(
                    user_id=user_id,
                    birthday=birthday
                )
                # Get updated list
                response, keyboard = self.get_excluded_birthdays(user_id)
                self.answer_callback_query(callback_query_id, f"Excluded {birthday.name}")
                self.edit_message(
                    user_id,
                    callback_query['message']['message_id'],
                    response,
                    keyboard
                )
                return

            elif callback_data.startswith("include_id_"):
                birthday_id = int(callback_data.split("_")[-1])
                birthday = GlobalBirthday.objects.get(id=birthday_id)
                UserBirthdayExclusion.objects.filter(
                    user_id=user_id,
                    birthday=birthday
                ).delete()
                # Get updated list
                response, keyboard = self.get_excluded_birthdays(user_id, for_inclusion=True)
                self.answer_callback_query(callback_query_id, f"Included {birthday.name}")
                self.edit_message(
                    user_id,
                    callback_query['message']['message_id'],
                    response,
                    keyboard
                )
                return

            elif callback_data in ["exclude_done", "include_done"]:
                response = "✅ Changes saved successfully!"
                self.answer_callback_query(callback_query_id)
                self.edit_message(
                    user_id,
                    callback_query['message']['message_id'],
                    response,
                    self.get_main_menu_keyboard(show_cancel=False)
                )
                return

            elif callback_data == "exclude_birthday":
                response, keyboard = self.get_excluded_birthdays(user_id)
                self.answer_callback_query(callback_query_id)
                self.send_message(user_id, response, keyboard)
                return

            elif callback_data == "include_birthday":
                response, keyboard = self.get_excluded_birthdays(user_id, for_inclusion=True)
                if isinstance(response, tuple):
                    response, keyboard = response
                self.answer_callback_query(callback_query_id)
                self.send_message(user_id, response, keyboard)
                return

            elif callback_data == "back_to_main":
                response = "What would you like to do?"
                self.answer_callback_query(callback_query_id)
                self.send_message(user_id, response, self.get_main_menu_keyboard(show_cancel=False))
                return

            elif callback_data == "help":
                response = self.cmd_help()
                self.answer_callback_query(callback_query_id)
                self.send_message(user_id, response, self.get_main_menu_keyboard(show_cancel=False))
                return

            elif callback_data == "cancel":
                # Clear any existing state
                UserState.objects.filter(user_id=user_id).delete()
                response = "Operation cancelled. What would you like to do?"
                self.answer_callback_query(callback_query_id)
                self.send_message(user_id, response, self.get_main_menu_keyboard(show_cancel=False))
                return

            self.answer_callback_query(callback_query_id)
            self.send_message(user_id, response, self.get_main_menu_keyboard())

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

    def cmd_my_birthday(self, message_text: str, user_id: str, user_name: str, *args) -> str:
        settings = UserBirthdaySettings.objects.filter(user_id=user_id).first()
        if not settings or not settings.birthday:
            return "You haven't set your birthday yet. Use the Add Birthday button to add your birthday."

        birthday = settings.birthday
        next_birthday = birthday.get_next_birthday()
        days_until = (next_birthday - timezone.now().date()).days
        age = birthday.get_age()
        persian_date = birthday.get_persian_date()

        response = [
            "🎂 Your Birthday Information:",
            f"\n📅 Gregorian Date: {birthday.birth_date}",
            f"🗓️ Persian Date: {persian_date}",
            f"\n🎈 Current Age: {age}",
            f"⏳ Days until next birthday: {days_until}"
        ]

        if settings.reminder_days:
            response.append(f"⏰ Reminder set for: {settings.reminder_days} days before")
        else:
            response.append("⏰ No reminder set")

        return "\n".join(response)

    def cmd_list_birthdays(self, message_text: str, user_id: str, *args) -> str:
        # Get all birthdays except excluded ones
        excluded_ids = UserBirthdayExclusion.objects.filter(user_id=user_id).values_list('birthday_id', flat=True)
        birthdays = GlobalBirthday.objects.exclude(id__in=excluded_ids).order_by('birth_date')

        if not birthdays:
            return "No birthdays in your view! Add some birthdays or check your exclusion settings."

        today = timezone.now().date()
        response = "🎂 All Birthdays:\n\n"
        
        for birthday in birthdays:
            next_birthday = birthday.get_next_birthday()
            days_until = (next_birthday - today).days
            persian_date = birthday.get_persian_date()
            
            response += (f"ID: {birthday.id}\n"
                        f"👤 {birthday.name}\n"
                        f"📅 Gregorian: {birthday.birth_date}\n"
                        f"📅 Persian: {persian_date}\n"
                        f"⏳ Days until birthday: {days_until}\n\n")
        
        return response

    def get_birthday_list_for_exclusion(self, user_id: str) -> str:
        """Get all birthdays except already excluded ones with interactive buttons."""
        # Get all birthdays except already excluded ones
        excluded_ids = UserBirthdayExclusion.objects.filter(user_id=user_id).values_list('birthday_id', flat=True)
        birthdays = GlobalBirthday.objects.exclude(id__in=excluded_ids).order_by('birth_date')

        if not birthdays:
            return "No birthdays available to exclude!"

        response = "🎂 Select birthdays to exclude:\n\n"
        buttons = []
        current_row = []
        
        for birthday in birthdays:
            current_row.append({
                "text": f"❌ {birthday.name}",
                "callback_data": f"exclude_id_{birthday.id}"
            })
            
            if len(current_row) == 2:  # Create rows of 2 buttons
                buttons.append(current_row)
                current_row = []
        
        if current_row:  # Add any remaining buttons
            buttons.append(current_row)
            
        # Add Done button at the bottom
        buttons.append([{"text": "✅ Done", "callback_data": "exclude_done"}])
        
        keyboard = self.create_inline_keyboard(buttons)
        return response, keyboard

    def get_excluded_birthdays(self, user_id: str, for_inclusion: bool = False) -> str:
        """Get list of excluded birthdays with interactive buttons."""
        excluded_birthdays = GlobalBirthday.objects.filter(
            id__in=UserBirthdayExclusion.objects.filter(user_id=user_id).values_list('birthday_id', flat=True)
        ).order_by('birth_date')

        if not excluded_birthdays:
            return "You haven't excluded any birthdays yet!"

        if for_inclusion:
            response = "🎂 Select birthdays to include:\n\n"
        else:
            response = "🎂 Currently excluded birthdays:\n\n"

        buttons = []
        current_row = []
        
        if for_inclusion:
            for birthday in excluded_birthdays:
                current_row.append({
                    "text": f"✅ {birthday.name}",
                    "callback_data": f"include_id_{birthday.id}"
                })
                
                if len(current_row) == 2:  # Create rows of 2 buttons
                    buttons.append(current_row)
                    current_row = []
            
            if current_row:  # Add any remaining buttons
                buttons.append(current_row)
                
            # Add Done button at the bottom
            buttons.append([{"text": "✅ Done", "callback_data": "include_done"}])
            
            keyboard = self.create_inline_keyboard(buttons)
            return response, keyboard
        else:
            for birthday in excluded_birthdays:
                response += (f"👤 {birthday.name}\n"
                           f"📅 Gregorian: {birthday.birth_date}\n"
                           f"📅 Persian: {birthday.get_persian_date()}\n\n")
            
            return response

    def cmd_help(self, *args) -> str:
        return ("Welcome to Birthday Reminder Bot! 🎉\n\n"
               "Use the buttons below to:\n"
               "• Add birthdays to the global list\n"
               "• Set reminder preferences\n"
               "• View your birthday info\n"
               "• List all birthdays\n"
               "• Manage birthday visibility\n"
               "• Get help\n\n"
               "You can also use these commands:\n"
               "/cancel - Cancel current operation\n"
               "/exclude - Exclude a birthday from your view\n"
               "/include - Include a previously excluded birthday\n\n"
               "Features:\n"
               "• Global birthday sharing\n"
               "• Duplicate detection\n"
               "• Persian calendar support\n"
               "• Customizable reminders\n"
               "• Birthday visibility management")

    def _notify_chat_members(self, chat_id: str, user_id: str, display_name: str, 
                           birth_date: datetime.date, persian_date: str) -> None:
        """Notify all chat members about a new birthday."""
        all_members = ChatMember.objects.filter(chat_id=chat_id).exclude(user_id=user_id)
        notification = (
            f"🎉 New Birthday Added! 🎉\n"
            f"{display_name} has set their birthday to:\n"
            f"Gregorian: {birth_date}\n"
            f"Persian: {persian_date}"
        )
        for member in all_members:
            self.send_message(member.user_id, notification) 

    def cmd_exclude(self, message_text: str, user_id: str, user_name: str, *args) -> str:
        """Handle the /exclude command to exclude birthdays from view."""
        response, keyboard = self.get_birthday_list_for_exclusion(user_id)
        if response != "No birthdays available to exclude!":
            # Set state for exclusion
            UserState.objects.update_or_create(
                user_id=user_id,
                defaults={'state': 'waiting_for_exclude'}
            )
        return response

    def cmd_include(self, message_text: str, user_id: str, user_name: str, *args) -> str:
        """Handle the /include command to include previously excluded birthdays."""
        response, keyboard = self.get_excluded_birthdays(user_id, for_inclusion=True)
        if response != "You haven't excluded any birthdays yet!":
            # Set state for inclusion
            UserState.objects.update_or_create(
                user_id=user_id,
                defaults={'state': 'waiting_for_include'}
            )
        return response