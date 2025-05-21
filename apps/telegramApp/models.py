from django.db import models
from django.utils import timezone
import jdatetime

# Create your models here.

class GlobalBirthday(models.Model):
    """Global birthday entries that can be shared across users"""
    name = models.CharField(max_length=100)  # Person's name
    birth_date = models.DateField()  # Gregorian date
    persian_birth_date = models.CharField(max_length=20, blank=True)  # Persian date stored as string
    added_by = models.CharField(max_length=100)  # Telegram user ID of first person who added this
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Ensure uniqueness based on name and date combination
        unique_together = ['name', 'birth_date']

    def save(self, *args, **kwargs):
        # Automatically convert and store Persian date whenever Gregorian date is saved
        if self.birth_date:
            persian_date = jdatetime.date.fromgregorian(date=self.birth_date)
            self.persian_birth_date = persian_date.strftime('%Y-%m-%d')
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

class UserBirthdayExclusion(models.Model):
    """Track which birthdays a user has excluded from their view/notifications"""
    user_id = models.CharField(max_length=100)  # Telegram user ID
    birthday = models.ForeignKey(GlobalBirthday, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user_id', 'birthday']

    def __str__(self):
        return f"{self.user_id} excluded {self.birthday.name}'s birthday"

class UserState(models.Model):
    """Track user conversation state for multi-step interactions"""
    user_id = models.CharField(max_length=100, unique=True)  # Telegram user ID
    state = models.CharField(max_length=50)  # Current state in conversation
    context = models.JSONField(default=dict)  # Store any context needed for the state
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"State for {self.user_id}: {self.state}"
