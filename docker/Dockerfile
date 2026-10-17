# syntax=docker/dockerfile:1

ARG PYTHON_VER=3.13

FROM python:${PYTHON_VER}-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_ENV=production

WORKDIR /app

COPY requirements requirements/
RUN pip install --no-cache-dir -r requirements/production.txt

COPY . .

# Bake the database into the image: it's read-only reference data, loaded offline.
RUN DJANGO_SECRET_KEY=build python manage.py migrate --noinput \
    && DJANGO_SECRET_KEY=build python manage.py import_places \
    && DJANGO_SECRET_KEY=build python manage.py import_fuel_stations --offline \
    && DJANGO_SECRET_KEY=build python manage.py collectstatic --noinput

RUN groupadd --gid 999 --system spotter \
    && useradd --uid 999 --gid 999 --system spotter \
    && chown -R spotter:spotter /app
USER spotter

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--preload"]
