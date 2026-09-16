#!/usr/bin/env bash
set -e
cd /app

# Exit 10 means "empty DB, please migrate". Disable set -e around this
# probe so the intentional non-zero status is not treated as a crash.
set +e
python <<'PY'
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "RealEstate.settings")
import django
django.setup()
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("SELECT to_regclass(%s)", ('public."baseApp_slide"',))
    slide_table = cursor.fetchone()[0]
    if slide_table:
        cursor.execute('SELECT COUNT(*) FROM "baseApp_slide"')
        count = cursor.fetchone()[0]
    else:
        count = 0

if count:
    print(f"Existing data detected ({count} slides); skipping migrate.")
    sys.exit(0)

print("Empty database; running migrate.")
sys.exit(10)
PY
status=$?
set -e
if [ "$status" -eq 10 ]; then
  python manage.py migrate --noinput
elif [ "$status" -ne 0 ]; then
  echo "Could not inspect database (status=$status); skipping migrate."
fi

exec python manage.py runserver 0.0.0.0:9000
