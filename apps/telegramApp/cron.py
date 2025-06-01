from apps.telegramApp.management.commands.send_birthday_reminder import Command
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

def send_automatic_birthday_reminders():
    """
    Send automatic birthday reminders to all users.
    This function is specifically designed to be called by cron jobs
    for daily automatic reminder processing.
    """
    try:
        args = []
        options = {
            'auto': True,
            'user_id': None
        }
        
        command_obj = Command()
        command_obj.handle(*args, **options)
        logger.info("Automatic birthday reminders sent successfully")
        
    except Exception as e:
        logger.error(f"Error in automatic birthday reminder cron job: {e}")
        raise


