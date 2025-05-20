from django.urls import path
from . import views

app_name = 'chatApp'

urlpatterns = [
    path('', views.ChatGPTView.as_view(), name='chat_gpt'),
]
