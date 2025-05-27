from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.telegramApp.models import GlobalBirthday, UserBirthdaySettings
from apps.telegramApp.bots.birthday_bot import BirthdayBot
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Sends birthday reminders. Can be used for manual testing or automatic daily reminders.'

    def add_arguments(self, parser):
        parser.add_argument('--user_id', type=str, help='Telegram user ID to send reminder to (for manual testing)')
        parser.add_argument('--auto', action='store_true', help='Run automatic reminders for all users')

    def handle(self, *args, **options):
        user_id = options.get('user_id')
        auto_mode = options.get('auto', False)

        if not user_id and not auto_mode:
            self.stdout.write(self.style.ERROR('Please provide either --user_id for manual testing or --auto for automatic reminders'))
            return

        try:
            # Initialize bot
            bot = BirthdayBot()

            if auto_mode:
                self.send_automatic_reminders(bot)
            else:
                self.send_manual_reminder(bot, user_id)

        except Exception as e:
            logger.error(f"Error sending birthday reminder: {e}")
            self.stdout.write(self.style.ERROR(f'Error sending birthday reminder: {str(e)}'))

    def send_automatic_reminders(self, bot):
        """Send automatic reminders to all users based on their reminder settings."""
        today = timezone.now().date()
        users = UserBirthdaySettings.objects.all()
        reminders_sent = 0

        for user in users:
            try:
                # Get all birthdays for this user
                birthdays = GlobalBirthday.objects.filter(added_by=user.user_id)
                if not birthdays:
                    continue

                for birthday in birthdays:
                    next_birthday = birthday.get_next_birthday()
                    days_until = (next_birthday - today).days
                    
                    # Get reminder days (individual setting or user default)
                    reminder_days = birthday.reminder_days or user.reminder_days

                    # Check if reminder should be sent
                    should_send = (
                        days_until <= reminder_days and  # Within reminder window
                        (not birthday.snoozed_until or birthday.snoozed_until <= today) and  # Not snoozed
                        (not birthday.last_reminder_sent or  # Never sent before
                         birthday.last_reminder_sent < next_birthday - timedelta(days=reminder_days))  # Not sent for this occurrence
                    )

                    if should_send:
                        # Format and send the reminder
                        message = self.format_reminder_message(birthday, days_until)
                        keyboard = self.create_reminder_keyboard(bot, birthday)
                        bot.send_message(user.user_id, message, keyboard)

                        # Update last reminder sent date
                        birthday.last_reminder_sent = today
                        birthday.save()
                        reminders_sent += 1

            except Exception as e:
                logger.error(f"Error sending automatic reminder to user {user.user_id}: {e}")
                continue

        self.stdout.write(
            self.style.SUCCESS(
                f'Automatic reminder job completed. Sent {reminders_sent} reminders.'
            )
        )

    def send_manual_reminder(self, bot, user_id):
        """Send a manual test reminder for the next birthday."""
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

        # Format and send the reminder
        message = self.format_reminder_message(birthday_obj, days_until)
        keyboard = self.create_reminder_keyboard(bot, birthday_obj)
        bot.send_message(user_id, message, keyboard)

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully sent birthday reminder to user {user_id} '
                f'for {birthday_obj.name}\'s birthday in {days_until} days'
            )
        )

    def format_reminder_message(self, birthday, days_until):
        """Format the reminder message."""
        if days_until == 0:
            message = f"🎉 Today is {birthday.name}'s birthday! 🎂"
        elif days_until == 1:
            message = f"🎈 Tomorrow is {birthday.name}'s birthday! 🎂"
        else:
            message = f"📅 {birthday.name}'s birthday is in {days_until} days! 🎂"

        message += f"\nDate: {birthday.birth_date}"
        message += f"\nPersian date: {birthday.persian_birth_date}"
        
        # Add zodiac sign
        zodiac = BirthdayBot().get_zodiac_sign(birthday.birth_date)
        message += f"\n{zodiac}"

        return message

    def create_reminder_keyboard(self, bot, birthday):
        """Create the reminder keyboard with snooze buttons."""
        buttons = [
            [
                {"text": "Snooze 1 day", "callback_data": f"snooze_{birthday.id}_1"},
                {"text": "Snooze 3 days", "callback_data": f"snooze_{birthday.id}_3"}
            ],
            [
                {"text": "Snooze 1 week", "callback_data": f"snooze_{birthday.id}_7"},
                {"text": "Dismiss", "callback_data": f"dismiss_reminder_{birthday.id}"}
            ]
        ]
        return bot.create_inline_keyboard(buttons) 