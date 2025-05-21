from datetime import datetime
from django.conf import settings
from django.utils import timezone
from typing import Optional, Dict, Any
import logging

from ..models import BirthdayReminder, ChatMember
from .base import TelegramBot

logger = logging.getLogger(__name__)

class BirthdayBot(TelegramBot):
    def __init__(self):
        token = settings.TELEGRAM_BIRTHDAY_BOT_TOKEN
        super().__init__(token)
        self.commands = {
            '/start': self.cmd_start,
            '/setbirthday': self.cmd_set_birthday,
            '/setreminder': self.cmd_set_reminder,
            '/mybirthday': self.cmd_my_birthday,
            '/listbirthdays': self.cmd_list_birthdays,
            '/help': self.cmd_help
        }

    def get_main_menu_keyboard(self) -> Dict:
        """Create the main menu keyboard."""
        buttons = [
            [{"text": "🎂 Set My Birthday", "callback_data": "set_birthday"}],
            [{"text": "⏰ Set Reminder", "callback_data": "set_reminder"}],
            [{"text": "🎈 My Birthday Info", "callback_data": "my_birthday"}],
            [{"text": "📋 List All Birthdays", "callback_data": "list_birthdays"}],
            [{"text": "❓ Help", "callback_data": "help"}]
        ]
        return self.create_inline_keyboard(buttons)

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

    def handle_callback_query(self, callback_query: Dict[str, Any]) -> None:
        """Handle callback queries from inline keyboard buttons."""
        try:
            chat_id = str(callback_query['message']['chat']['id'])
            user_id = str(callback_query['from']['id'])
            user_name = f"{callback_query['from'].get('first_name', '')} {callback_query['from'].get('last_name', '')}".strip()
            callback_data = callback_query['data']
            callback_query_id = callback_query['id']

            if callback_data == "set_birthday":
                response = "Please send your birthday in the format:\nYYYY-MM-DD Your Name"
            elif callback_data == "set_reminder":
                response = "Please send the number of days before birthdays you want to be reminded:"
            elif callback_data == "my_birthday":
                response = self.cmd_my_birthday("", chat_id, user_id, user_name)
            elif callback_data == "list_birthdays":
                response = self.cmd_list_birthdays("", chat_id, user_id, user_name)
            elif callback_data == "help":
                response = self.cmd_help()
            else:
                response = "Unknown command"

            self.answer_callback_query(callback_query_id)
            self.send_message(chat_id, response, self.get_main_menu_keyboard())

        except Exception as e:
            logger.error(f"Error handling callback query: {e}")
            self.send_message(chat_id, f"An error occurred: {str(e)}", self.get_main_menu_keyboard())

    def cmd_start(self, *args) -> str:
        return ("Welcome to Birthday Reminder Bot!\n\nCommands:\n"
               "/setbirthday YYYY-MM-DD Your Name - Set your birthday\n"
               "/setreminder X - Set reminder X days before birthdays\n"
               "/mybirthday - Show your birthday info\n"
               "/listbirthdays - List all birthdays in this chat\n"
               "/help - Show this help message")

    def cmd_set_birthday(self, message_text: str, chat_id: str, user_id: str, user_name: str) -> str:
        parts = message_text.split()
        try:
            if len(parts) < 3:
                return "Please use format: /setbirthday YYYY-MM-DD Your Name"
            
            birth_date = datetime.strptime(parts[1], '%Y-%m-%d').date()
            display_name = ' '.join(parts[2:])
            
            reminder, created = BirthdayReminder.objects.get_or_create(
                chat_id=chat_id,
                user_id=user_id,
                defaults={
                    'birth_date': birth_date,
                    'user_name': display_name
                }
            )
            if not created:
                reminder.birth_date = birth_date
                reminder.user_name = display_name
                reminder.save()

            persian_date = reminder.get_persian_date()
            self._notify_chat_members(chat_id, user_id, display_name, birth_date, persian_date)
            
            return f"Birthday set to:\nGregorian: {birth_date}\nPersian: {persian_date}"

        except ValueError:
            return "Invalid date format. Please use: /setbirthday YYYY-MM-DD Your Name"

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

    def cmd_set_reminder(self, message_text: str, chat_id: str, user_id: str, *args) -> str:
        parts = message_text.split()
        try:
            if len(parts) != 2:
                return "Please use format: /setreminder X (where X is number of days)"
            
            days = int(parts[1])
            if days < 0:
                return "Please enter a positive number of days"

            reminder = BirthdayReminder.objects.filter(chat_id=chat_id, user_id=user_id).first()
            if not reminder:
                return "Please set your birthday first using /setbirthday YYYY-MM-DD Your Name"

            reminder.reminder_days = days
            reminder.save()
            return f"You will be notified {days} days before each birthday in this chat"

        except ValueError:
            return "Please enter a valid number of days"

    def cmd_my_birthday(self, message_text: str, chat_id: str, user_id: str, *args) -> str:
        reminder = BirthdayReminder.objects.filter(chat_id=chat_id, user_id=user_id).first()
        if not reminder:
            return "You haven't set your birthday yet. Use /setbirthday YYYY-MM-DD Your Name"

        next_birthday = reminder.get_next_birthday()
        days_until = (next_birthday - timezone.now().date()).days
        age = reminder.get_age()
        persian_date = reminder.get_persian_date()

        return (f"Your birthday:\nGregorian: {reminder.birth_date}\n"
                f"Persian: {persian_date}\n"
                f"Current age: {age}\n"
                f"Days until next birthday: {days_until}\n"
                f"Reminder set for: {reminder.reminder_days} days before")

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