from django.shortcuts import render
from django.http import HttpResponse
from django.views import generic
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import json
import openai
from django.conf import settings
import requests
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
    else:
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_DICTIONARY_BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    response = requests.post(url, json=data)
    return response.json()   

# Handle incoming messages
def handle_update(request):
    # Extract relevant information from the Update (JSONized)
    # read the structure from here
    # https://core.telegram.org/bots/api#update

    try:
        # Get the raw JSON data from the request
        received_data = json.loads(request.body.decode('utf-8'))
        message_text = received_data.get('message', {}).get('text', '')
        chat_id = received_data.get('message', {}).get('chat', {}).get('id')

        # I used this to recognize the Bot which the user is working with!!
        secret_token = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')

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

