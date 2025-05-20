from django.db import models
from django.utils import timezone
import jdatetime

# Create your models here.

class BirthdayReminder(models.Model):
    chat_id = models.CharField(max_length=100)  # The chat where birthday was registered
    user_id = models.CharField(max_length=100)  # Telegram user ID
    user_name = models.CharField(max_length=100)  # Display name
    birth_date = models.DateField()
    reminder_days = models.IntegerField(default=1)  # Days before birthday to send reminder
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['chat_id', 'user_id']  # One birthday per user per chat

    def get_persian_date(self):
        return jdatetime.date.fromgregorian(date=self.birth_date)

    def get_next_birthday(self):
        today = timezone.now().date()
        birthday_this_year = self.birth_date.replace(year=today.year)
        
        if birthday_this_year < today:
            birthday_this_year = birthday_this_year.replace(year=today.year + 1)
        
        return birthday_this_year

    def get_age(self):
        today = timezone.now().date()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )

    def __str__(self):
        return f"{self.user_name}'s Birthday - {self.birth_date}"

class ChatMember(models.Model):
    """Keep track of chat members for notifications"""
    chat_id = models.CharField(max_length=100)
    user_id = models.CharField(max_length=100)
    user_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['chat_id', 'user_id']

    def __str__(self):
        return f"{self.user_name} in chat {self.chat_id}"
