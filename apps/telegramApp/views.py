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
from typing import Optional, Dict, Any
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

    def send_message(self, chat_id: str, text: str) -> Dict[str, Any]:
        """Send a message to a specific chat."""
        url = f"{self.base_url}/sendMessage"
        data = {"chat_id": chat_id, "text": text}
        try:
            response = requests.post(url, json=data)
            return response.json()
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return {"error": str(e)}

    @abstractmethod
    def handle_command(self, message: Dict[str, Any]) -> Optional[str]:
        """Handle incoming commands - to be implemented by specific bots."""
        pass

class BirthdayBot(TelegramBot):
    def __init__(self):
        super().__init__(settings.TELEGRAM_BIRTHDAY_BOT_TOKEN)
        self.commands = {
            '/start': self.cmd_start,
            '/setbirthday': self.cmd_set_birthday,
            '/setreminder': self.cmd_set_reminder,
            '/mybirthday': self.cmd_my_birthday,
            '/listbirthdays': self.cmd_list_birthdays,
            '/help': self.cmd_help
        }

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

            command = message_text.split()[0].lower()
            handler = self.commands.get(command)
            
            if handler:
                return handler(message_text, chat_id, user_id, user_name)
            return None
            
        except Exception as e:
            logger.error(f"Error handling birthday command: {e}")
            return f"An error occurred while processing your request: {str(e)}"

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
                return HttpResponse('Invalid bot token', status=400)

            # Handle the message
            response = bot.handle_command(data.get('message', {}))
            if response:
                chat_id = str(data.get('message', {}).get('chat', {}).get('id'))
                bot.send_message(chat_id, response)

            return HttpResponse('Success', status=200)

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return HttpResponse('Invalid JSON', status=400)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return HttpResponse('Internal Server Error', status=500)

