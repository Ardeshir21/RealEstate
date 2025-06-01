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
        birthday_messages_sent = 0

        for user in users:
            try:
                # Get all birthdays for this user
                birthdays = GlobalBirthday.objects.filter(added_by=user.user_id)
                if not birthdays:
                    continue

                for birthday in birthdays:
                    next_birthday = birthday.get_next_birthday()
                    days_until = (next_birthday - today).days
                    
                    # Always send birthday message on the exact date
                    if days_until == 0:
                        message = self.format_reminder_message(birthday, days_until)
                        # No keyboard on birthday message - it's a pure celebration!
                        bot.send_message(user.user_id, message, None)
                        birthday_messages_sent += 1
                        continue  # Skip reminder logic on birthday
                    
                    # Handle reminders for upcoming birthdays
                    reminder_days = birthday.reminder_days or user.reminder_days

                    # Check if reminder should be sent
                    should_send = (
                        days_until <= reminder_days and  # Within reminder window
                        days_until > 0 and  # Not today (handled above)
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
                f'Automatic job completed. Sent {birthday_messages_sent} birthday messages and {reminders_sent} reminders.'
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

        # Format and send the message
        message = self.format_reminder_message(birthday_obj, days_until)
        
        # If it's the birthday, send without keyboard
        if days_until == 0:
            bot.send_message(user_id, message, None)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully sent birthday message to user {user_id} '
                    f'for {birthday_obj.name}\'s birthday today!'
                )
            )
        else:
            # For reminders, include the keyboard
            keyboard = self.create_reminder_keyboard(bot, birthday_obj)
            bot.send_message(user_id, message, keyboard)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully sent birthday reminder to user {user_id} '
                    f'for {birthday_obj.name}\'s birthday in {days_until} days'
                )
            )

    def format_reminder_message(self, birthday, days_until):
        """Format the reminder message based on the type of notification."""
        today = timezone.now().date()
        
        # Birthday message (on the day)
        if days_until == 0:
            message = (
                f"🎉🎉🎉 HAPPY BIRTHDAY! 🎉🎉🎉\n\n"
                f"Today is {birthday.name}'s special day! 🎂\n"
                f"Wishing them a wonderful birthday filled with joy and happiness! 🎈\n"
                f"Don't forget to send your warmest wishes! 🎁"
            )
        
        # Reminder message (first notification before birthday)
        elif not birthday.last_reminder_sent or birthday.last_reminder_sent < today - timedelta(days=1):
            if days_until == 1:
                message = (
                    f"🎈 Birthday Tomorrow! 🎈\n\n"
                    f"Don't forget - tomorrow is {birthday.name}'s birthday! 🎂\n"
                    f"Time to prepare your wishes! ✨"
                )
            else:
                message = (
                    f"📅 Upcoming Birthday Reminder 📅\n\n"
                    f"{birthday.name}'s birthday is coming up in {days_until} days! 🎂\n"
                    f"Start planning how you'll celebrate! 🎈"
                )
        
        # Snoozed reminder message
        else:
            if days_until == 1:
                message = (
                    f"⏰ Snoozed Reminder: Birthday Tomorrow! ⏰\n\n"
                    f"This is your snoozed reminder - {birthday.name}'s birthday is tomorrow! 🎂\n"
                    f"Time to get ready! 🎈"
                )
            else:
                message = (
                    f"⏰ Snoozed Birthday Reminder ⏰\n\n"
                    f"As requested, reminding you about {birthday.name}'s birthday!\n"
                    f"It's coming up in {days_until} days! 🎂"
                )

        # Add common information for all types
        message += f"\n\nDate: {birthday.birth_date}"
        message += f"\nPersian date: {birthday.persian_birth_date}"
        
        # Add zodiac sign
        zodiac = BirthdayBot().get_zodiac_sign(birthday.birth_date)
        message += f"\n{zodiac}"

        return message

    def create_reminder_keyboard(self, bot, birthday):
        """Create the reminder keyboard with snooze buttons."""
        today = timezone.now().date()
        next_birthday = birthday.get_next_birthday()
        days_until = (next_birthday - today).days
        
        buttons = []
        snooze_options = []
        
        # Only add snooze options that are valid (less than days until birthday)
        if days_until > 1:
            snooze_options.append({"text": "Snooze 1 day", "callback_data": f"snooze_{birthday.id}_1"})
        if days_until > 3:
            snooze_options.append({"text": "Snooze 3 days", "callback_data": f"snooze_{birthday.id}_3"})
        if days_until > 7:
            snooze_options.append({"text": "Snooze 1 week", "callback_data": f"snooze_{birthday.id}_7"})
            
        # Add snooze buttons in pairs if available
        while len(snooze_options) >= 2:
            buttons.append(snooze_options[:2])
            snooze_options = snooze_options[2:]
        
        # Add any remaining single snooze button
        if snooze_options:
            buttons.append(snooze_options)
            
        # Always add dismiss button in its own row
        buttons.append([{"text": "Dismiss", "callback_data": f"dismiss_reminder_{birthday.id}"}])
        
        return bot.create_inline_keyboard(buttons) 