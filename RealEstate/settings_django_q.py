# =============================================================================
# Django-Q2 — async task queue
# https://django-q2.readthedocs.io/en/master/configure.html
# Broker: same PostgreSQL DB as the main application (orm = "default").
# Worker process is started via: python manage.py qcluster
# =============================================================================

Q_CLUSTER = {
    'name': 'RealEstate',
    'workers': 2,
    'timeout': 1800,
    'retry': 2400,
    'orm': 'default',
}

# schedule_type: 'D' = daily, 'W' = weekly, 'I' = minutes
Q_SCHEDULE = {
    'send_automatic_birthday_reminders': {
        'func': 'apps.telegramApp.cron.send_automatic_birthday_reminders',
        'schedule_type': 'D',
        'hour': 9,
        'minute': 0,
        'repeats': -1,
    },
}
