from django.core.management.base import BaseCommand
from django.utils import timezone
from telegramApp.models import GlobalBirthday, UserBirthdaySettings
from telegramApp.views import send_message
from telegramApp.bots.base import TelegramBot
import jdatetime

class Command(BaseCommand):
    help = 'Send birthday reminders to users'

    def create_snooze_keyboard(self, birthday_id: int, days_until: int) -> dict:
        """Create snooze keyboard based on remaining days."""
        buttons = []
        snooze_options = []
        
        # Add snooze options if there are enough days remaining
        if days_until > 3:
            snooze_options.append({"text": "⏰ 3 days before", "callback_data": f"snooze_{birthday_id}_3"})
        if days_until > 2:
            snooze_options.append({"text": "⏰ 2 days before", "callback_data": f"snooze_{birthday_id}_2"})
        if days_until > 1:
            snooze_options.append({"text": "⏰ 1 day before", "callback_data": f"snooze_{birthday_id}_1"})
            
        # Create rows of 2 buttons each
        for i in range(0, len(snooze_options), 2):
            row = snooze_options[i:i+2]
            buttons.append(row)
            
        # Add dismiss button
        buttons.append([{"text": "✅ Dismiss", "callback_data": f"dismiss_reminder_{birthday_id}"}])
        
        return TelegramBot.create_inline_keyboard(buttons)

    def handle(self, *args, **options):
        today = timezone.now().date()
        persian_today = jdatetime.date.today()

        # Get all users with settings
        user_settings = UserBirthdaySettings.objects.all()

        for user in user_settings:
            # Get birthdays added by this user
            birthdays = GlobalBirthday.objects.filter(added_by=user.user_id)

            for birthday in birthdays:
                next_birthday = birthday.get_next_birthday()
                days_until = (next_birthday - today).days

                # Send exact day notification
                if days_until == 0:
                    message = (
                        f"🎉 Happy Birthday! 🎂\n\n"
                        f"Today is {birthday.name}'s birthday!\n"
                        f"📅 Date: {birthday.birth_date}\n"
                        f"🗓️ Persian: {birthday.get_persian_date()}"
                    )
                    try:
                        send_message(user.user_id, message)
                        birthday.last_reminder_sent = today
                        birthday.save()
                    except Exception as e:
                        self.stderr.write(f"Failed to send birthday notification to user {user.user_id}: {e}")
                    continue

                # Check if it's time to send a reminder
                reminder_days = birthday.reminder_days or user.reminder_days
                should_send = (
                    days_until <= reminder_days and  # Within reminder window
                    (birthday.last_reminder_sent is None or  # Never sent before
                     birthday.last_reminder_sent < today) and  # Not sent today
                    (birthday.snoozed_until is None or  # Not snoozed
                     birthday.snoozed_until <= today)  # Snooze expired
                )

                if should_send:
                    message = (
                        f"🎂 Birthday Reminder!\n\n"
                        f"👤 {birthday.name}'s birthday is in {days_until} days!\n"
                        f"📅 Date: {birthday.birth_date}\n"
                        f"🗓️ Persian: {birthday.get_persian_date()}\n\n"
                        f"Want to be reminded later? Use the snooze buttons below:"
                    )
                    try:
                        # Create snooze keyboard
                        keyboard = self.create_snooze_keyboard(birthday.id, days_until)
                        
                        # Send message with snooze buttons
                        send_message(user.user_id, message, keyboard)
                        
                        # Update last reminder sent date
                        birthday.last_reminder_sent = today
                        birthday.save()
                    except Exception as e:
                        self.stderr.write(f"Failed to send reminder to user {user.user_id}: {e}") 