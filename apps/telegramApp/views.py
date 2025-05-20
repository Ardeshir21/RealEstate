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
############################################################
# Telegram Bot
# Token and webhook URL
# https://api.telegram.org/bot<Token>/METHOD_NAME
# WEBHOOK_URL = 'https://www.gammaturkey.com/telegram-dictionary-bot/'

# set webhook for your bots by calling the following url
# Dictionary:
# https://api.telegram.org/bot<token>/setWebhook?url=https://www.gammaturkey.com/telegram/&secret_token=Dictionary

# Phrase Helper
# https://api.telegram.org/bot<token>/setWebhook?url=https://www.gammaturkey.com/telegram/&secret_token=Phrase


def send_message(bot_secret_word, chat_id, text):
    if bot_secret_word == 'Phrase':
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_TOPIC_BOT_TOKEN}/sendMessage"
    elif bot_secret_word == 'Birthday':
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BIRTHDAY_BOT_TOKEN}/sendMessage"
    else:
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_DICTIONARY_BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    response = requests.post(url, json=data)
    return response.json()

def handle_birthday_commands(message_text, chat_id, user_id, user_name):
    parts = message_text.split()
    command = parts[0].lower()

    # Always ensure the user is registered in the chat
    ChatMember.objects.get_or_create(
        chat_id=chat_id,
        user_id=user_id,
        defaults={'user_name': user_name}
    )

    if command == '/start':
        return ("Welcome to Birthday Reminder Bot!\n\nCommands:\n"
               "/setbirthday YYYY-MM-DD Your Name - Set your birthday\n"
               "/setreminder X - Set reminder X days before birthdays\n"
               "/mybirthday - Show your birthday info\n"
               "/listbirthdays - List all birthdays in this chat\n"
               "/help - Show this help message")

    elif command == '/setbirthday':
        try:
            if len(parts) < 3:
                return "Please use format: /setbirthday YYYY-MM-DD Your Name"
            
            birth_date = datetime.strptime(parts[1], '%Y-%m-%d').date()
            display_name = ' '.join(parts[2:])  # Everything after the date is the name
            
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
            
            # Notify all chat members about the new birthday
            all_members = ChatMember.objects.filter(chat_id=chat_id).exclude(user_id=user_id)
            for member in all_members:
                notification = (
                    f"🎉 New Birthday Added! 🎉\n"
                    f"{display_name} has set their birthday to:\n"
                    f"Gregorian: {birth_date}\n"
                    f"Persian: {persian_date}"
                )
                send_message(bot_secret_word='Birthday', chat_id=member.user_id, text=notification)

            return f"Birthday set to:\nGregorian: {birth_date}\nPersian: {persian_date}"

        except ValueError:
            return "Invalid date format. Please use: /setbirthday YYYY-MM-DD Your Name"

    elif command == '/setreminder':
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

    elif command == '/mybirthday':
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

    elif command == '/listbirthdays':
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

    elif command == '/help':
        return ("Birthday Bot Commands:\n"
               "/setbirthday YYYY-MM-DD Your Name - Set your birthday\n"
               "/setreminder X - Set reminder X days before birthdays\n"
               "/mybirthday - Show your birthday info\n"
               "/listbirthdays - List all birthdays in this chat\n"
               "/help - Show this help message")

    return None

# Handle incoming messages
def handle_update(request):
    # Extract relevant information from the Update (JSONized)
    # read the structure from here
    # https://core.telegram.org/bots/api#update

    try:
        # Get the raw JSON data from the request
        received_data = json.loads(request.body.decode('utf-8'))
        message = received_data.get('message', {})
        message_text = message.get('text', '')
        chat_id = str(message.get('chat', {}).get('id'))
        user = message.get('from', {})
        user_id = str(user.get('id'))
        user_name = user.get('first_name', '')
        if user.get('last_name'):
            user_name += f" {user.get('last_name')}"

        # I used this to recognize the Bot which the user is working with!!
        secret_token = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')

        # Handle Birthday Bot
        if secret_token == 'Birthday':
            response = handle_birthday_commands(message_text, chat_id, user_id, user_name)
            if response:
                send_message(bot_secret_word=secret_token, chat_id=chat_id, text=response)
                return

        # Handle the extracted information
        if message_text == '/start':
            send_message(bot_secret_word=secret_token, chat_id=chat_id, text="Hello, I'm your dictionary bot!")
        else:
            # OpenAI API client
            openai_client = openai.OpenAI(api_key=settings.CHATGPT_API)

            # Construct prompt and get definition from OpenAI
            prompt = f"{message_text}"

            # Base on Robot ID determine the system content dynamically
            if secret_token=='Phrase':
                system_content = f"I'm looking to enhance my English vocabulary for discussions about {prompt}. Could you provide me with some words or phrases, \
                                    along with examples of how they are used in informal situations? This way, I can better express myself when talking about {prompt}."
            else:
                system_content = f"Provide a comprehensive dictionary entry for the word {prompt} like Longman Contemporary style, including:  \n- Part of speech \
                                \n- Definition  \n- Phonetics (how to pronounce the word) \n- Two examples of how to use the word in a sentence \
                                \n- Its frequency or commonality. Is it common to use it in informal conversation? If yes, give two examples of that. \n-What other common alternative words that I can use instead of {prompt}? \
                                \n- Give some of the common collocation for this word. \n Do we have any common phrasal verb which contains {prompt}, give me an example of them."

            # call OpenAI
            try:
                bot_response = openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages = [
                        {"role": "user", "content": f'{prompt}'},
                        {"role": "system", "content": system_content}
                    ],
                    temperature=0.8,
                    max_tokens=3000,
                )

                definition = bot_response.choices[0].message.content
                # send the ai reply to telegram chat
                send_message(bot_secret_word=secret_token, chat_id=chat_id, text=definition)

            except Exception as e:
                send_message(bot_secret_word=secret_token, chat_id=chat_id, text=f"An error occurred: {e}")
    
    except Exception as e:
        # Handle JSON decoding errors
        send_message(bot_secret_word=secret_token, chat_id=chat_id, text=f"Error decoding JSON: {e}")


# View to handle webhook
class TelegramDictionaryBotView(generic.View):
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):   
        # if not bot.get_webhook_info().url:
        #     bot.set_webhook(url=WEBHOOK_URL)
        return super().dispatch(request, *args, **kwargs)


    def post(self, request, *args, **kwargs):
        handle_update(request)
        return HttpResponse('Success', status=200)

