# syntax=docker/dockerfile:1.5
FROM python:3.12-slim AS builder

RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt \
    apt-get update && \
    apt-get install \
      --yes \
      --no-install-recommends \
      curl && \
    curl \
      --silent \
      --show-error \
      --location \
      --output install-poetry.py \
      https://install.python-poetry.org && \
    python3 install-poetry.py && \
    python3 -m venv --without-pip /opt/venv

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

COPY --link pyproject.toml poetry.lock /

RUN --mount=type=cache,target=/root/.cache/pypoetry \
    /root/.local/bin/poetry install --no-root --only=main

FROM python:3.12-slim

COPY --link --from=builder /opt/venv /opt/venv

WORKDIR /usr/src/app
EXPOSE 8000
ENTRYPOINT ["/opt/venv/bin/python", "manage.py"]
CMD ["runserver", "0.0.0.0:8000"]
