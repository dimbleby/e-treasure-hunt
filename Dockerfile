# syntax=docker/dockerfile:1.9
FROM python:3.12-slim

WORKDIR /venv

COPY --link pyproject.toml uv.lock /venv/

RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

ENV PATH="/venv/.venv/bin:$PATH"

WORKDIR /app

EXPOSE 8000
ENTRYPOINT ["python", "manage.py"]
CMD ["runserver", "0.0.0.0:8000"]
