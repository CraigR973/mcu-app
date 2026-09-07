FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

COPY apps/api/requirements.lock ./requirements.lock
RUN python -m pip install --no-cache-dir --upgrade pip==26.2.1 \
    && python -m pip install --no-cache-dir --require-hashes -r requirements.lock

COPY apps/api/src/ ./src/
COPY apps/api/migrations/ ./migrations/
COPY apps/api/alembic.ini ./alembic.ini

EXPOSE 8000

# A failed migration must stop the deployment. exec gives uvicorn PID 1 so
# Railway shutdown signals reach it directly.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
