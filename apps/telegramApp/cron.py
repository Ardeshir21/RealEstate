from apps.telegramApp.management.commands.send_birthday_reminder import Command
import logging

logger = logging.getLogger(__name__)

def send_automatic_birthday_reminders():
    """
    Send automatic birthday reminders to all users.
    Called daily at 09:00 UTC by django-q2 (Q_SCHEDULE).
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


