# Immagine multi-architettura: funziona su PC Linux (amd64) e Raspberry Pi 4/5 a 64 bit (arm64)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    DEBUG=false MEDIA_ROOT=/data/media

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN SECRET_KEY=build python manage.py collectstatic --noinput \
    && useradd -r -u 1000 gpverse && mkdir -p /data/media && chown -R gpverse /data /app

USER gpverse
EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--timeout", "60"]
