from django.core.management.base import BaseCommand
from django.utils import timezone
from telegramApp.models import GlobalBirthday, UserBirthdaySettings
from telegramApp.views import send_message
import jdatetime

class Command(BaseCommand):
    help = 'Send birthday reminders to users'

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

                # Check if it's time to send a reminder
                if days_until <= user.reminder_days:
                    message = (
                        f"🎂 Birthday Reminder!\n\n"
                        f"👤 {birthday.name}'s birthday is in {days_until} days!\n"
                        f"📅 Date: {birthday.birth_date}\n"
                        f"🗓️ Persian: {birthday.get_persian_date()}"
                    )
                    try:
                        send_message(user.user_id, message)
                    except Exception as e:
                        self.stderr.write(f"Failed to send reminder to user {user.user_id}: {e}") 