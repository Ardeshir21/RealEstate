#!/usr/bin/env python
"""Run birthday reminders daily at 09:00 UTC without a host cron daemon."""
from __future__ import annotations

import datetime
import subprocess
import sys
import time

HOUR = 9
MINUTE = 0


def seconds_until_next_run() -> float:
    now = datetime.datetime.now(datetime.timezone.utc)
    target = now.replace(hour=HOUR, minute=MINUTE, second=0, microsecond=0)
    if now >= target:
        target = target + datetime.timedelta(days=1)
    return (target - now).total_seconds()


def main() -> None:
    print("Birthday cron runner started (09:00 UTC).", flush=True)
    while True:
        wait = max(1.0, seconds_until_next_run())
        print(f"Sleeping {wait:.0f}s until next reminder run.", flush=True)
        time.sleep(wait)
        print("Running send_birthday_reminder --auto", flush=True)
        result = subprocess.run(
            [sys.executable, "/app/manage.py", "send_birthday_reminder", "--auto"],
            check=False,
        )
        print(f"Reminder command exited {result.returncode}", flush=True)


if __name__ == "__main__":
    main()
