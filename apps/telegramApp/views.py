from django.shortcuts import render
from django.http import HttpResponse
from django.views import generic
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import json
import openai
from django.conf import settings
import requests
from datetime import datetime
import jdatetime
from .models import BirthdayReminder, ChatMember
from django.utils import timezone
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)
############################################################
# Telegram Bot
# Token and webhook URL
# https://api.telegram.org/bot<Token>/METHOD_NAME
# WEBHOOK_URL = 'https://www.gammaturkey.com/telegram/'

# set webhook for your bots by calling the following url
# Dictionary:
# https://api.telegram.org/bot<token>/setWebhook?url=https://www.gammaturkey.com/telegram/&secret_token=Dictionary

# Phrase Helper
# https://api.telegram.org/bot<token>/setWebhook?url=https://www.gammaturkey.com/telegram/&secret_token=Phrase

# Birthday Reminder
# https://api.telegram.org/bot<token>/setWebhook?url=https://www.gammaturkey.com/telegram/&secret_token=Birthday



class TelegramBot(ABC):
    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"

    def send_message(self, chat_id: str, text: str, reply_markup: Optional[Dict] = None) -> Dict[str, Any]:
        """Send a message to a specific chat with optional keyboard markup."""
        url = f"{self.base_url}/sendMessage"
        data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            data["reply_markup"] = reply_markup
        try:
            response = requests.post(url, json=data)
            return response.json()
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            logger.error(f"Response content: {getattr(response, 'content', 'N/A')}")
            return {"error": str(e)}

    def create_inline_keyboard(self, buttons: List[List[Dict[str, str]]]) -> Dict:
        """Create an inline keyboard markup from a list of button rows."""
        return {"inline_keyboard": buttons}

    def answer_callback_query(self, callback_query_id: str, text: Optional[str] = None) -> Dict[str, Any]:
        """Answer a callback query from an inline keyboard button."""
        url = f"{self.base_url}/answerCallbackQuery"
        data = {"callback_query_id": callback_query_id}
        if text:
            data["text"] = text
        try:
            response = requests.post(url, json=data)
            return response.json()
        except Exception as e:
            logger.error(f"Error answering callback query: {e}")
            return {"error": str(e)}

    @abstractmethod
    def handle_command(self, message: Dict[str, Any]) -> Optional[str]:
        """Handle incoming commands - to be implemented by specific bots."""
        pass

    @abstractmethod
    def handle_callback_query(self, callback_query: Dict[str, Any]) -> None:
        """Handle callback queries from inline keyboards - to be implemented by specific bots."""
        pass

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

class DictionaryBot(TelegramBot):
    def __init__(self):
        super().__init__(settings.TELEGRAM_DICTIONARY_BOT_TOKEN)
        self.openai_client = openai.OpenAI(api_key=settings.CHATGPT_API)

    def handle_command(self, message: Dict[str, Any]) -> Optional[str]:
        try:
            message_text = message.get('text', '')
            
            if message_text == '/start':
                return "Hello, I'm your dictionary bot!"
            
            return self._get_dictionary_definition(message_text)
        except Exception as e:
            logger.error(f"Error in DictionaryBot: {e}")
            return f"An error occurred: {str(e)}"

    def _get_dictionary_definition(self, word: str) -> str:
        system_content = (
            f"Provide a comprehensive dictionary entry for the word {word} like Longman Contemporary style, including:  \n"
            "- Part of speech \n"
            "- Definition  \n"
            "- Phonetics (how to pronounce the word) \n"
            "- Two examples of how to use the word in a sentence \n"
            "- Its frequency or commonality. Is it common to use it in informal conversation? If yes, give two examples of that. \n"
            f"- What other common alternative words that I can use instead of {word}? \n"
            "- Give some of the common collocation for this word. \n"
            f"Do we have any common phrasal verb which contains {word}, give me an example of them."
        )

        response = self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": word},
                {"role": "system", "content": system_content}
            ],
            temperature=0.8,
            max_tokens=3000,
        )
        
        return response.choices[0].message.content

class PhraseBot(TelegramBot):
    def __init__(self):
        super().__init__(settings.TELEGRAM_TOPIC_BOT_TOKEN)
        self.openai_client = openai.OpenAI(api_key=settings.CHATGPT_API)

    def handle_command(self, message: Dict[str, Any]) -> Optional[str]:
        try:
            message_text = message.get('text', '')
            
            if message_text == '/start':
                return "Hello, I'm your phrase helper bot!"
            
            return self._get_phrase_suggestions(message_text)
        except Exception as e:
            logger.error(f"Error in PhraseBot: {e}")
            return f"An error occurred: {str(e)}"

    def _get_phrase_suggestions(self, topic: str) -> str:
        system_content = (
            f"I'm looking to enhance my English vocabulary for discussions about {topic}. "
            "Could you provide me with some words or phrases, along with examples of how "
            "they are used in informal situations?"
        )

        response = self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": topic},
                {"role": "system", "content": system_content}
            ],
            temperature=0.8,
            max_tokens=3000,
        )
        
        return response.choices[0].message.content

class BotFactory:
    @staticmethod
    def create_bot(secret_token: str) -> Optional[TelegramBot]:
        if secret_token == 'Birthday':
            return BirthdayBot()
        elif secret_token == 'Phrase':
            return PhraseBot()
        else:
            return DictionaryBot()

class TelegramWebhookView(generic.View):
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        try:
            # Parse incoming update
            data = json.loads(request.body.decode('utf-8'))
            secret_token = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
            
            # Create appropriate bot instance
            bot = BotFactory.create_bot(secret_token)
            if not bot:
                logger.error("Invalid bot token received: %s", secret_token)
                return HttpResponse('Invalid bot token', status=400)

            # Handle callback query if present
            if 'callback_query' in data:
                bot.handle_callback_query(data['callback_query'])
                return HttpResponse('Success', status=200)

            # Handle regular message
            message = data.get('message', {})
            chat_id = str(message.get('chat', {}).get('id'))
            user = message.get('from', {})
            user_id = str(user.get('id'))
            username = user.get('username', '')
            first_name = user.get('first_name', '')
            last_name = user.get('last_name', '')

            response = bot.handle_command(message)
            if response:
                bot.send_message(chat_id, response)
            
            return HttpResponse('Success', status=200)

        except json.JSONDecodeError as e:
            logger.error("JSON decode error: %s", str(e))
            return HttpResponse('Invalid JSON', status=400)
        except Exception as e:
            logger.error("Unexpected error processing telegram update: %s", str(e), exc_info=True)
            return HttpResponse('Internal Server Error', status=500)

