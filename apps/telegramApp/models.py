from django.db import models
from django.utils import timezone
import jdatetime
import re

# Create your models here.

class TelegramAdmin(models.Model):
    """Admin users with full privileges"""
    user_id = models.CharField(max_length=100, unique=True)  # Telegram user ID
    user_name = models.CharField(max_length=100)  # Display name
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Admin: {self.user_name}"

class GlobalBirthday(models.Model):
    """Birthday entries that are private to each user"""
    name = models.CharField(max_length=255)  # Person's name
    birth_date = models.DateField()  # Gregorian date
    persian_birth_date = models.CharField(max_length=20, blank=True)  # Persian date stored as string
    added_by = models.CharField(max_length=255)  # Telegram user ID of the person who added this
    telegram_id = models.CharField(max_length=255, null=True, blank=True)  # Telegram ID if it's their own birthday
    reminder_days = models.IntegerField(null=True, blank=True)  # Days before birthday to send reminder (null means use default)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Ensure uniqueness based on name, date and added_by combination
        unique_together = ['name', 'birth_date', 'added_by']

    @staticmethod
    def is_persian_date(date_str: str) -> bool:
        """Check if the given date string is in Persian format (YYYY/MM/DD)"""
        if not re.match(r'^\d{4}[/-]\d{1,2}[/-]\d{1,2}$', date_str):
            return False
        try:
            year, month, day = map(int, re.split('[/-]', date_str))
            # Basic validation for Persian date
            return 1 <= month <= 12 and 1 <= day <= 31 and year >= 1200 and year <= 1500
        except ValueError:
            return False

    @staticmethod
    def parse_date(date_str: str):
        """Parse date string in either Gregorian (YYYY-MM-DD) or Persian (YYYY/MM/DD) format"""
        date_str = date_str.strip()
        
        # Replace Persian numbers with English numbers if present
        persian_to_english = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
        date_str = date_str.translate(persian_to_english)
        
        # Standardize separators
        date_str = date_str.replace('/', '-')
        
        if GlobalBirthday.is_persian_date(date_str):
            # Convert Persian to Gregorian
            year, month, day = map(int, date_str.split('-'))
            persian_date = jdatetime.date(year, month, day)
            return persian_date.togregorian(), date_str.replace('-', '/')
        else:
            # Assume Gregorian
            try:
                year, month, day = map(int, date_str.split('-'))
                gregorian_date = timezone.datetime(year, month, day).date()
                persian_date = jdatetime.date.fromgregorian(date=gregorian_date)
                return gregorian_date, persian_date.strftime('%Y/%m/%d')
            except ValueError as e:
                raise ValueError("Invalid date format. Use YYYY-MM-DD for Gregorian or YYYY/MM/DD for Persian")

    def save(self, *args, **kwargs):
        # If birth_date is a string, parse it first
        if isinstance(self.birth_date, str):
            self.birth_date, self.persian_birth_date = self.parse_date(self.birth_date)
        # If birth_date is already a date object, just update persian_birth_date
        elif self.birth_date and not self.persian_birth_date:
            persian_date = jdatetime.date.fromgregorian(date=self.birth_date)
            self.persian_birth_date = persian_date.strftime('%Y/%m/%d')
        super().save(*args, **kwargs)

    def get_persian_date(self):
        """Get Persian date string"""
        return self.persian_birth_date

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
        return f"{self.name}'s Birthday - {self.birth_date} ({self.persian_birth_date})"

class UserBirthdaySettings(models.Model):
    """User-specific settings and birthday mappings"""
    user_id = models.CharField(max_length=100)  # Telegram user ID
    user_name = models.CharField(max_length=100)  # Display name
    birthday = models.ForeignKey(GlobalBirthday, on_delete=models.CASCADE, null=True, blank=True)  # User's own birthday
    reminder_days = models.IntegerField(default=1)  # Days before birthday to send reminder
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user_id', 'birthday']  # Each user can only have one setting per birthday

    def __str__(self):
        return f"Settings for {self.user_name}"

class UserState(models.Model):
    """Track user conversation state for multi-step interactions"""
    user_id = models.CharField(max_length=100, unique=True)  # Telegram user ID
    state = models.CharField(max_length=50)  # Current state in conversation
    context = models.JSONField(default=dict)  # Store any context needed for the state
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"State for {self.user_id}: {self.state}"
