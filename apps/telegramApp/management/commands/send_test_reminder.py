from django.core.management.base import BaseCommand
from django.utils import timezone
from telegramApp.models import GlobalBirthday, UserBirthdaySettings
from telegramApp.views import send_message
from telegramApp.bots.base import TelegramBot
import jdatetime

class Command(BaseCommand):
    help = 'Send a test birthday reminder to a specific user'

    def add_arguments(self, parser):
        parser.add_argument('--user_id', type=str, required=True, help='Telegram user ID to send reminder to')
        parser.add_argument('--birthday_id', type=int, required=False, help='Optional: Specific birthday ID to send reminder for')
        parser.add_argument('--days', type=int, default=3, help='Optional: Days until birthday (default: 3)')

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
        user_id = options['user_id']
        birthday_id = options.get('birthday_id')
        days_until = options['days']

        try:
            # Get user settings
            user_settings = UserBirthdaySettings.objects.get(user_id=user_id)

            # Get birthdays to send reminders for
            if birthday_id:
                birthdays = GlobalBirthday.objects.filter(id=birthday_id, added_by=user_id)
            else:
                birthdays = GlobalBirthday.objects.filter(added_by=user_id)

            if not birthdays:
                self.stdout.write(self.style.ERROR(f'No birthdays found for user {user_id}'))
                return

            for birthday in birthdays:
                if days_until == 0:
                    message = (
                        f"🎉 Happy Birthday! 🎂\n\n"
                        f"Today is {birthday.name}'s birthday!\n"
                        f"📅 Date: {birthday.birth_date}\n"
                        f"🗓️ Persian: {birthday.get_persian_date()}"
                    )
                else:
                    message = (
                        f"🎂 Birthday Reminder!\n\n"
                        f"👤 {birthday.name}'s birthday is in {days_until} days!\n"
                        f"📅 Date: {birthday.birth_date}\n"
                        f"🗓️ Persian: {birthday.get_persian_date()}\n\n"
                        f"Want to be reminded later? Use the snooze buttons below:"
                    )

                try:
                    # Create snooze keyboard for non-zero days
                    keyboard = self.create_snooze_keyboard(birthday.id, days_until) if days_until > 0 else None
                    
                    # Send message with snooze buttons
                    send_message(user_id, message, keyboard)
                    
                    self.stdout.write(self.style.SUCCESS(
                        f'Successfully sent test reminder for {birthday.name} to user {user_id}'))

                except Exception as e:
                    self.stderr.write(f"Failed to send reminder to user {user_id}: {e}")

        except UserBirthdaySettings.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User {user_id} not found'))
        except Exception as e:
            self.stderr.write(f"An error occurred: {e}") 