from django.core.management.base import BaseCommand
from apps.telegramApp.models import GlobalBirthday, UserBirthdaySettings
from datetime import datetime, timedelta
import random
import names  # You'll need to pip install names

class Command(BaseCommand):
    help = 'Creates dummy birthdays for testing'

    def add_arguments(self, parser):
        parser.add_argument('--user_id', type=str, default='68405550')
        parser.add_argument('--count', type=int, default=300)

    def handle(self, *args, **options):
        user_id = options['user_id']
        count = options['count']

        # Create or get user settings
        user_settings, _ = UserBirthdaySettings.objects.get_or_create(
            user_id=user_id,
            defaults={
                'user_name': 'Test User',
                'reminder_days': 1
            }
        )

        # List of common Persian names
        persian_names = [
            'Ali', 'Mohammad', 'Reza', 'Hassan', 'Hossein', 'Mehdi', 'Ahmad', 'Amir',
            'Hamid', 'Saeed', 'Maryam', 'Fatima', 'Zahra', 'Sara', 'Narges', 'Leila',
            'Mahsa', 'Shirin', 'Nasrin', 'Parisa'
        ]

        # Generate random birthdays
        start_date = datetime(1950, 1, 1).date()
        end_date = datetime(2010, 12, 31).date()
        days_between = (end_date - start_date).days

        birthdays_created = 0
        attempts = 0
        max_attempts = count * 2  # Allow some room for duplicates

        self.stdout.write('Generating birthdays...')

        while birthdays_created < count and attempts < max_attempts:
            attempts += 1

            # Generate random date
            random_days = random.randrange(days_between)
            birthday_date = start_date + timedelta(days=random_days)

            # Generate name (alternating between Western and Persian names)
            if random.random() < 0.5:
                name = names.get_full_name()
            else:
                first_name = random.choice(persian_names)
                last_name = random.choice(persian_names)
                name = f"{first_name} {last_name}"

            try:
                # Create birthday
                birthday = GlobalBirthday(
                    name=name,
                    birth_date=birthday_date,
                    added_by=user_id
                )
                birthday.save()
                birthdays_created += 1

                if birthdays_created % 10 == 0:
                    self.stdout.write(f'Created {birthdays_created} birthdays...')

            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Failed to create birthday: {str(e)}'))
                continue

        self.stdout.write(self.style.SUCCESS(
            f'Successfully created {birthdays_created} test birthdays for user {user_id}')) 