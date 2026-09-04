FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PYTHONPATH=/app/backend

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY backend ./backend

RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev

CMD ["uv", "run", "celery", "-A", "app.celery_app:celery_app", "worker", "--loglevel=INFO"]
