FROM python:3.10-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY ./requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/logs /app/static /app/media \
    && sed -i 's/\r$//' ./docker/mainframe/dev-start.sh ./docker/cron/crontab \
    && chmod +x ./docker/mainframe/dev-start.sh

EXPOSE 9000

ARG APP_NAME=RealEstate
ENV APP_NAME=${APP_NAME}

CMD gunicorn --config ./docker/mainframe/gunicorn-cfg.py "${APP_NAME}.wsgi:application"
