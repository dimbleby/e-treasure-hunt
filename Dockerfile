# syntax=docker/dockerfile:1.19
FROM python:3.14-slim

WORKDIR /app

COPY --link pyproject.toml uv.lock /app/

ENV UV_PROJECT_ENVIRONMENT="/venv/" \
    PATH="/venv/bin:$PATH"

RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

EXPOSE 8000
ENTRYPOINT ["python", "manage.py"]
CMD ["runserver", "0.0.0.0:8000"]
