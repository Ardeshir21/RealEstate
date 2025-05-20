from django.core.management.base import BaseCommand
from django.utils import timezone
from telegramApp.models import BirthdayReminder, ChatMember
from telegramApp.views import send_message
import jdatetime

class Command(BaseCommand):
    help = 'Send birthday reminders to users'

    def handle(self, *args, **options):
        today = timezone.now().date()
        persian_today = jdatetime.date.today()

        # Get all birthday reminders
        reminders = BirthdayReminder.objects.all()

        for reminder in reminders:
            next_birthday = reminder.get_next_birthday()
            days_until = (next_birthday - today).days

            # Get all members in the chat to notify them
            chat_members = ChatMember.objects.filter(chat_id=reminder.chat_id)
            
            # For each member, check their reminder preference and notify if needed
            for member in chat_members:
                member_pref = BirthdayReminder.objects.filter(
                    chat_id=reminder.chat_id,
                    user_id=member.user_id
                ).first()
                
                # If member hasn't set any preferences, use default (1 day)
                reminder_days = member_pref.reminder_days if member_pref else 1
                
                # Check if we need to send a reminder
                if days_until == reminder_days:
                    age_will_be = reminder.get_age() + 1
                    persian_birthday = reminder.get_persian_date()
                    
                    message = (
                        f"🎂 Birthday Reminder! 🎂\n\n"
                        f"{reminder.user_name}'s birthday is in {days_until} days!\n"
                        f"Birthday date (Gregorian): {reminder.birth_date}\n"
                        f"Birthday date (Persian): {persian_birthday}\n"
                        f"Will turn {age_will_be} years old!\n\n"
                        f"Don't forget to send your wishes! 🎉"
                    )

                    send_message(bot_secret_word='Birthday', chat_id=member.user_id, text=message)
                    self.stdout.write(
                        self.style.SUCCESS(f'Sent reminder about {reminder.user_name} to {member.user_name}')
                    ) 