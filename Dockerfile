# syntax=docker/dockerfile:1.7
FROM python:3.12 AS builder

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install poetry==1.8.3 && \
    python3 -m venv --without-pip /opt/venv

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

COPY --link pyproject.toml poetry.lock /

RUN --mount=type=cache,target=/root/.cache/pypoetry \
    poetry install --only=main

FROM python:3.12-slim

COPY --link --from=builder /opt/venv /opt/venv

WORKDIR /usr/src/app
EXPOSE 8000
ENTRYPOINT ["/opt/venv/bin/python", "manage.py"]
CMD ["runserver", "0.0.0.0:8000"]
