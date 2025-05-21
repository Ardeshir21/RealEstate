from django.core.management.base import BaseCommand
from django.utils import timezone
from telegramApp.models import GlobalBirthday, UserBirthdaySettings, UserBirthdayExclusion
from telegramApp.views import send_message
import jdatetime

class Command(BaseCommand):
    help = 'Send birthday reminders to users'

    def handle(self, *args, **options):
        today = timezone.now().date()
        persian_today = jdatetime.date.today()

        # Get all birthdays
        birthdays = GlobalBirthday.objects.all()

        # Get all users with settings
        user_settings = UserBirthdaySettings.objects.all()

        for user in user_settings:
            # Get excluded birthdays for this user
            excluded_ids = UserBirthdayExclusion.objects.filter(
                user_id=user.user_id
            ).values_list('birthday_id', flat=True)

            # Check each non-excluded birthday
            for birthday in birthdays.exclude(id__in=excluded_ids):
                next_birthday = birthday.get_next_birthday()
                days_until = (next_birthday - today).days

                # Check if we need to send a reminder based on user's preference
                if days_until == user.reminder_days:
                    age_will_be = birthday.get_age() + 1
                    persian_birthday = birthday.get_persian_date()
                    
                    message = (
                        f"🎂 Birthday Reminder! 🎂\n\n"
                        f"{birthday.name}'s birthday is in {days_until} days!\n"
                        f"Birthday date (Gregorian): {birthday.birth_date}\n"
                        f"Birthday date (Persian): {persian_birthday}\n"
                        f"Will turn {age_will_be} years old!\n\n"
                        f"Don't forget to send your wishes! 🎉"
                    )

                    send_message(bot_secret_word='Birthday', chat_id=user.user_id, text=message)
                    self.stdout.write(
                        self.style.SUCCESS(f'Sent reminder about {birthday.name} to {user.user_name}')
                    ) 