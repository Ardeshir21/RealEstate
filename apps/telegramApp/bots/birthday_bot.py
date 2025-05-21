from datetime import datetime
from django.conf import settings
from django.utils import timezone
from typing import Optional, Dict, Any
import logging
import jdatetime
import re

from ..models import BirthdayReminder, ChatMember, UserState
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
            '/help': self.cmd_help
        }

    def get_main_menu_keyboard(self, show_cancel: bool = True) -> Dict:
        """Create the main menu keyboard.
        
        Args:
            show_cancel: Whether to show the cancel button
        """
        buttons = [
            [{"text": "🎂 Set My Birthday", "callback_data": "set_birthday"}],
            [{"text": "⏰ Set Reminder", "callback_data": "set_reminder"}],
            [{"text": "🎈 My Birthday Info", "callback_data": "my_birthday"}],
            [{"text": "📋 List All Birthdays", "callback_data": "list_birthdays"}],
            [{"text": "❓ Help", "callback_data": "help"}],
        ]
        
        if show_cancel:
            buttons.append([{"text": "❌ Cancel", "callback_data": "cancel"}])
            
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
            chat_id = str(message.get('chat', {}).get('id'))
            user = message.get('from', {})
            user_id = str(user.get('id'))
            user_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()

            # Register chat member
            ChatMember.objects.get_or_create(
                chat_id=chat_id,
                user_id=user_id,
                defaults={'user_name': user_name}
            )

            if message_text == '/start':
                welcome_text = ("Welcome to Birthday Reminder Bot! 🎉\n\n"
                              "Please use the buttons below to interact with me:")
                self.send_message(chat_id, welcome_text, self.get_main_menu_keyboard())
                return None

            # Check if user is in a conversation state
            user_state = UserState.objects.filter(chat_id=chat_id, user_id=user_id).first()
            if user_state:
                return self.handle_state_response(message_text, chat_id, user_id, user_name, user_state)

            command = message_text.split()[0].lower()
            handler = self.commands.get(command)
            
            if handler:
                response = handler(message_text, chat_id, user_id, user_name)
                if response:
                    self.send_message(chat_id, response, self.get_main_menu_keyboard())
                return None
            return None
            
        except Exception as e:
            logger.error(f"Error handling birthday command: {e}")
            return f"An error occurred while processing your request: {str(e)}"

    def handle_state_response(self, message_text: str, chat_id: str, user_id: str, user_name: str, user_state: UserState) -> Optional[str]:
        """Handle responses based on user's current state."""
        try:
            if user_state.state == "waiting_for_birthday":
                try:
                    # Parse the Gregorian date
                    birth_date = datetime.strptime(message_text.strip(), '%Y-%m-%d').date()
                    
                    # Save the birthday
                    reminder, created = BirthdayReminder.objects.get_or_create(
                        chat_id=chat_id,
                        user_id=user_id,
                        defaults={
                            'birth_date': birth_date,
                            'user_name': user_name
                        }
                    )
                    if not created:
                        reminder.birth_date = birth_date
                        reminder.save()

                    # Clear the state
                    user_state.delete()

                    persian_date = reminder.get_persian_date()
                    self._notify_chat_members(chat_id, user_id, user_name, birth_date, persian_date)
                    
                    response = f"✅ Birthday successfully set to:\nGregorian: {birth_date}\nPersian: {persian_date}"
                    self.send_message(chat_id, response, self.get_main_menu_keyboard())
                    return None
                except ValueError:
                    return "❌ Invalid date format. Please use YYYY-MM-DD (e.g., 1990-12-31)\nOr click Cancel to go back to main menu."

            elif user_state.state == "waiting_for_reminder":
                try:
                    days = int(message_text.strip())
                    if days < 0:
                        return "❌ Please enter a positive number of days\nOr click Cancel to go back to main menu."

                    reminder = BirthdayReminder.objects.filter(chat_id=chat_id, user_id=user_id).first()
                    if not reminder:
                        return "Please set your birthday first!"

                    reminder.reminder_days = days
                    reminder.save()

                    # Clear the state
                    user_state.delete()

                    response = f"✅ You will be notified {days} days before each birthday in this chat"
                    self.send_message(chat_id, response, self.get_main_menu_keyboard())
                    return None
                except ValueError:
                    return "❌ Please enter a valid number\nOr click Cancel to go back to main menu."

        except Exception as e:
            logger.error(f"Error in handle_state_response: {e}")
            user_state.delete()  # Clear state on error
            return "An error occurred. Please try again."

    def handle_callback_query(self, callback_query: Dict[str, Any]) -> None:
        """Handle callback queries from inline keyboard buttons."""
        try:
            chat_id = str(callback_query['message']['chat']['id'])
            user_id = str(callback_query['from']['id'])
            user_name = f"{callback_query['from'].get('first_name', '')} {callback_query['from'].get('last_name', '')}".strip()
            callback_data = callback_query['data']
            callback_query_id = callback_query['id']

            if callback_data == "set_birthday":
                # Set state for birthday input
                UserState.objects.update_or_create(
                    chat_id=chat_id,
                    user_id=user_id,
                    defaults={'state': 'waiting_for_birthday'}
                )
                response = ("Please enter your birthday in YYYY-MM-DD format\n"
                          "For example: 1990-12-31\n\n"
                          "Click Cancel to go back to main menu.")

            elif callback_data == "set_reminder":
                # Set state for reminder input
                UserState.objects.update_or_create(
                    chat_id=chat_id,
                    user_id=user_id,
                    defaults={'state': 'waiting_for_reminder'}
                )
                response = ("Please enter the number of days before birthdays you want to be reminded\n"
                          "For example: 7\n\n"
                          "Click Cancel to go back to main menu.")

            elif callback_data == "my_birthday":
                response = self.cmd_my_birthday("", chat_id, user_id, user_name)
                self.answer_callback_query(callback_query_id)
                self.send_message(chat_id, response, self.get_main_menu_keyboard(show_cancel=False))
                return

            elif callback_data == "list_birthdays":
                response = self.cmd_list_birthdays("", chat_id, user_id, user_name)
                self.answer_callback_query(callback_query_id)
                self.send_message(chat_id, response, self.get_main_menu_keyboard(show_cancel=False))
                return

            elif callback_data == "help":
                response = self.cmd_help()
                self.answer_callback_query(callback_query_id)
                self.send_message(chat_id, response, self.get_main_menu_keyboard(show_cancel=False))
                return

            elif callback_data == "cancel":
                # Clear any existing state
                UserState.objects.filter(chat_id=chat_id, user_id=user_id).delete()
                response = "Operation cancelled. What would you like to do?"

            self.answer_callback_query(callback_query_id)
            self.send_message(chat_id, response, self.get_main_menu_keyboard())

        except Exception as e:
            logger.error(f"Error handling callback query: {e}")
            self.send_message(chat_id, f"An error occurred: {str(e)}", self.get_main_menu_keyboard())

    def cmd_cancel(self, *args) -> str:
        """Cancel current operation and clear state."""
        chat_id = args[1]
        user_id = args[2]
        UserState.objects.filter(chat_id=chat_id, user_id=user_id).delete()
        return "Operation cancelled. What would you like to do?"

    def cmd_start(self, *args) -> str:
        return ("Welcome to Birthday Reminder Bot! 🎉\n\n"
               "Use the buttons below to:\n"
               "• Set your birthday\n"
               "• Set reminder days\n"
               "• View your birthday info\n"
               "• List all birthdays\n"
               "• Get help\n\n"
               "You can also use /cancel at any time to cancel the current operation.")

    def cmd_my_birthday(self, message_text: str, chat_id: str, user_id: str, *args) -> str:
        reminder = BirthdayReminder.objects.filter(chat_id=chat_id, user_id=user_id).first()
        if not reminder:
            return "You haven't set your birthday yet. Use the Set Birthday button to add your birthday."

        next_birthday = reminder.get_next_birthday()
        days_until = (next_birthday - timezone.now().date()).days
        age = reminder.get_age()
        persian_date = reminder.get_persian_date()

        response = [
            "🎂 Your Birthday Information:",
            f"\n📅 Gregorian Date: {reminder.birth_date}",
            f"🗓️ Persian Date: {persian_date}",
            f"\n🎈 Current Age: {age}",
            f"⏳ Days until next birthday: {days_until}"
        ]

        if reminder.reminder_days:
            response.append(f"⏰ Reminder set for: {reminder.reminder_days} days before")
        else:
            response.append("⏰ No reminder set")

        return "\n".join(response)

    def cmd_list_birthdays(self, message_text: str, chat_id: str, *args) -> str:
        birthdays = BirthdayReminder.objects.filter(chat_id=chat_id).order_by('birth_date')
        if not birthdays:
            return "No birthdays set in this chat yet!"

        today = timezone.now().date()
        response = "🎂 Birthdays in this chat:\n\n"
        
        for birthday in birthdays:
            next_birthday = birthday.get_next_birthday()
            days_until = (next_birthday - today).days
            persian_date = birthday.get_persian_date()
            
            response += (f"👤 {birthday.user_name}\n"
                        f"📅 Gregorian: {birthday.birth_date}\n"
                        f"📅 Persian: {persian_date}\n"
                        f"⏳ Days until birthday: {days_until}\n\n")
        
        return response

    def cmd_help(self, *args) -> str:
        return self.cmd_start()

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