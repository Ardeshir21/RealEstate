from django.urls import path
from . import views

app_name = 'telegramApp'

urlpatterns = [
    path('', views.TelegramDictionaryBotView.as_view(), name='telegram_bot'),
]
