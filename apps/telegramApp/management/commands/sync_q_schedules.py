"""Upsert Django-Q Schedule rows from settings.Q_SCHEDULE."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone


def _next_run(*, schedule_type: str, hour: int = 0, minute: int = 0, week: int | None = None):
    now = timezone.now()
    if timezone.is_aware(now):
        now = timezone.localtime(now)
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if schedule_type == 'D':
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    if schedule_type == 'W':
        target_weekday = 0 if week is None else int(week)
        days_ahead = (target_weekday - candidate.weekday()) % 7
        candidate = candidate + timedelta(days=days_ahead)
        if candidate <= now:
            candidate += timedelta(days=7)
        return candidate

    if schedule_type == 'M':
        candidate = candidate.replace(day=1)
        if candidate <= now:
            if candidate.month == 12:
                candidate = candidate.replace(year=candidate.year + 1, month=1)
            else:
                candidate = candidate.replace(month=candidate.month + 1)
        return candidate

    return candidate if candidate > now else candidate + timedelta(days=1)


class Command(BaseCommand):
    help = 'Sync settings.Q_SCHEDULE entries into django_q.Schedule (create or update by name).'

    def handle(self, *args, **options):
        from django_q.models import Schedule

        schedule_map = getattr(settings, 'Q_SCHEDULE', {}) or {}
        if not schedule_map:
            self.stdout.write(self.style.WARNING('Q_SCHEDULE is empty.'))
            return

        allowed = {
            'func', 'hook', 'args', 'kwargs', 'schedule_type',
            'minutes', 'repeats', 'cron', 'cluster', 'next_run',
        }

        known = set(schedule_map.keys())
        for obj in Schedule.objects.exclude(name__in=known):
            self.stdout.write(self.style.WARNING(f'Deleting stale schedule: {obj.name}'))
            obj.delete()

        for name, cfg in schedule_map.items():
            schedule_type = cfg.get('schedule_type', Schedule.DAILY)
            defaults = {
                'func': cfg['func'],
                'schedule_type': schedule_type,
                'repeats': cfg.get('repeats', -1),
                'cron': None,
            }
            if 'args' in cfg:
                defaults['args'] = str(cfg['args'])
            if 'kwargs' in cfg:
                defaults['kwargs'] = str(cfg['kwargs'])
            if 'minutes' in cfg and cfg['minutes'] is not None:
                defaults['minutes'] = cfg['minutes']
            if 'cluster' in cfg:
                defaults['cluster'] = cfg['cluster']

            if schedule_type in (Schedule.DAILY, Schedule.WEEKLY, Schedule.MONTHLY, 'D', 'W', 'M'):
                defaults['next_run'] = _next_run(
                    schedule_type=schedule_type,
                    hour=int(cfg.get('hour', 0)),
                    minute=int(cfg.get('minute', 0)),
                    week=cfg.get('week'),
                )

            defaults = {k: v for k, v in defaults.items() if k in allowed}

            obj, created = Schedule.objects.update_or_create(
                name=name,
                defaults=defaults,
            )
            action = 'Created' if created else 'Updated'
            next_run = getattr(obj, 'next_run', None)
            extra = f' (next_run={next_run})' if next_run else ''
            self.stdout.write(f'{action} schedule: {name} -> {obj.func}{extra}')

        self.stdout.write(self.style.SUCCESS(f'Synced {len(schedule_map)} schedule(s).'))
