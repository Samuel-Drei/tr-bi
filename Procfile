web: python manage.py migrate --noinput && python manage.py preparar && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120
