from django.http import HttpResponse
from django.views import generic
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import json
import logging
from typing import Optional

from .bots.birthday_bot import BirthdayBot
from .bots.dictionary_bot import DictionaryBot
from .bots.phrase_bot import PhraseBot
from .bots.voice_transcription_bot import VoiceTranscriptionBot
from .bots.base import TelegramBot

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

# Voice Transcription
# https://api.telegram.org/bot<token>/setWebhook?url=https://www.gammaturkey.com/telegram/&secret_token=Voice

class BotFactory:
    @staticmethod
    def create_bot(secret_token: str) -> Optional[TelegramBot]:
        if secret_token == 'Birthday':
            return BirthdayBot()
        elif secret_token == 'Phrase':
            return PhraseBot()
        elif secret_token == 'Voice':
            return VoiceTranscriptionBot()
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

            # Handle both text and voice messages
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

