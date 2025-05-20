from django.shortcuts import render
from django.http import JsonResponse
from django.views import generic
from django.conf import settings
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q
import json
import openai
from apps.baseApp import models


# Here is the Extra Context ditionary which is used in get_context_data of Views classes
def get_extra_context():
    extraContext = {
        'DEBUG_VALUE': settings.DEBUG,
        # Default page for FAQ section.
        'navbar_FAQ': 'all'
        }
    return extraContext



# ChatGPT
class ChatGPTView(generic.TemplateView):
    template_name = 'chatApp/chat_gpt.html'

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Append extraContext
        context.update(get_extra_context())
        context['slideContent'] = models.Slide.objects.get(useFor__exact='ABOUT_US', active__exact=True)
        context['pageTitle'] = 'ASK ME'
        return context

    def post(self, request):

        # Get the user's message from the query string
        message = request.POST.get('message', '')

        # Get the current chat log from the cookie
        chat_log = request.COOKIES.get('chat_log')
        if chat_log:
            chat_log = json.loads(chat_log)
        else:
            chat_log = [{"role": "system", "content": "You are a helpful assistant."}]

        # Initialize the OpenAI API client
        client = openai.OpenAI(api_key=settings.CHATGPT_API,)

        # Create a new chat completion if there is no previous chat log
        if not chat_log:
            bot_response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                # prompt=message,
                temperature=0.8,
                max_tokens=3000,
                messages=chat_log,
            )
            chat_log.append({"role": "user", "content": message})
            chat_log.append({"role": "system", "content": bot_response.choices[0].message.content})
        else:
            chat_log[-1]["role"] = "user"
            chat_log[-1]["content"] = message
            bot_response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                # prompt=chat_log[-1]["content"],
                temperature=0.8,
                max_tokens=3000,
                messages=chat_log,
            )
            chat_log.append({"role": "system", "content": bot_response.choices[0].message.content})

        # Store the updated chat log in a cookie
        chat_log_json = json.dumps(chat_log)
        response = JsonResponse({'question': message,
                                 'message': bot_response.choices[0].message.content})
        response.set_cookie('chat_log', chat_log_json)

        # Return the chatbot's response as a JSON object
        return response
    