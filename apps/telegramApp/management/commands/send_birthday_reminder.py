from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.telegramApp.models import GlobalBirthday, UserBirthdaySettings
from apps.telegramApp.bots.birthday_bot import BirthdayBot
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Sends a reminder message for the next upcoming birthday for a specific Telegram user ID'

    def add_arguments(self, parser):
        parser.add_argument('--user_id', type=str, required=True, help='Telegram user ID to send reminder to')

    def handle(self, *args, **options):
        user_id = options['user_id']

        try:
            # Initialize bot
            bot = BirthdayBot()
            
            # Get user settings
            user_settings = UserBirthdaySettings.objects.filter(user_id=user_id).first()
            if not user_settings:
                self.stdout.write(self.style.ERROR(f'No settings found for user {user_id}'))
                return

            # Get all birthdays for this user
            birthdays = GlobalBirthday.objects.filter(added_by=user_id)
            if not birthdays:
                self.stdout.write(self.style.ERROR(f'No birthdays found for user {user_id}'))
                return

            # Get today's date
            today = timezone.now().date()

            # Find the next upcoming birthday
            next_birthday = None
            days_until = float('inf')
            birthday_obj = None

            for birthday in birthdays:
                next_date = birthday.get_next_birthday()
                days_to_birthday = (next_date - today).days

                if days_to_birthday < days_until:
                    days_until = days_to_birthday
                    next_birthday = next_date
                    birthday_obj = birthday

            if not next_birthday or not birthday_obj:
                self.stdout.write(self.style.ERROR('No upcoming birthdays found'))
                return

            # Format the reminder message
            if days_until == 0:
                message = f"🎉 Today is {birthday_obj.name}'s birthday! 🎂"
            elif days_until == 1:
                message = f"🎈 Tomorrow is {birthday_obj.name}'s birthday! 🎂"
            else:
                message = f"📅 {birthday_obj.name}'s birthday is in {days_until} days! 🎂"

            message += f"\nDate: {birthday_obj.birth_date}"
            message += f"\nPersian date: {birthday_obj.persian_birth_date}"
            
            # Add zodiac sign
            zodiac = bot.get_zodiac_sign(birthday_obj.birth_date)
            message += f"\n{zodiac}"

            # Create snooze buttons
            buttons = [
                [
                    {"text": "Snooze 1 day", "callback_data": f"snooze_{birthday_obj.id}_1"},
                    {"text": "Snooze 3 days", "callback_data": f"snooze_{birthday_obj.id}_3"}
                ],
                [
                    {"text": "Snooze 1 week", "callback_data": f"snooze_{birthday_obj.id}_7"},
                    {"text": "Dismiss", "callback_data": f"dismiss_reminder_{birthday_obj.id}"}
                ]
            ]
            keyboard = bot.create_inline_keyboard(buttons)

            # Send the message
            bot.send_message(user_id, message, keyboard)

            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully sent birthday reminder to user {user_id} '
                    f'for {birthday_obj.name}\'s birthday in {days_until} days'
                )
            )

        except Exception as e:
            logger.error(f"Error sending birthday reminder: {e}")
            self.stdout.write(
                self.style.ERROR(f'Error sending birthday reminder: {str(e)}')
            ) 