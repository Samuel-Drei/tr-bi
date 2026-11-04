FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN DJANGO_SECRET_KEY=build DJANGO_DEBUG=0 python manage.py collectstatic --noinput

RUN useradd -m app && chown -R app /app
USER app

EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py preparar && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120"]
