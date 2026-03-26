# Copilot Instructions — e-treasure-hunt

## Build & Run

Package management uses **uv** (not pip). Python **3.14+** is required.

```shell
uv sync --extra azure        # install all dependencies including Azure extras
uv run ruff check .           # lint
uv run ruff format --check .  # format check
uv run mypy .                 # type check
uv run pytest                 # run all tests
uv run pytest hunt/tests/test_views.py            # run one test file
uv run pytest hunt/tests/test_views.py::test_name # run a single test
```

Django management commands use `uv run python manage.py <command>`.

## Architecture

This is a **Django 6** application for running location-based treasure hunts. Teams log in, view clue images, and submit GPS coordinates to advance through levels.

### Project layout

- **`treasure/`** — Django project package (settings, root URL conf, ASGI/WSGI).
- **`hunt/`** — The single Django app containing all game logic.
- **`admin_scripts/`** — Standalone scripts for level validation, upload, download, and winner analysis. Not part of the Django app.
- **`azure/`** — Terraform infrastructure definitions for Azure deployment.

### Key modules in `hunt/`

| Module | Purpose |
|---|---|
| `models.py` | `Level`, `Hint`, `HuntInfo` (team progress), `HuntEvent` (audit log), `ChatMessage`, `AppSetting` (singleton config) |
| `views.py` | Function-based views for the player-facing hunt and admin management UI |
| `apiviews.py` | DRF `ModelViewSet` for levels and hints (admin-only REST API at `/api/levels/`) |
| `hint_request.py` | Hint request/release logic with dynamic delay based on team standings |
| `levels.py` | Level loading and coordinate search (GPS proximity check via geopy) |
| `level_mgr.py` | Level upload from the management UI |
| `chat/consumers.py` | Async WebSocket consumer for per-team, per-level chat (Django Channels) |
| `chat/routing.py` | WebSocket URL routing (`level/<int:level>/`) |
| `utils.py` | `AuthenticatedHttpRequest` type alias, `no_players_during_lockout` decorator, lockout logic |
| `constants.py` | `HINTS_PER_LEVEL = 5` |
| `third_party/apimixin.py` | `AllowPUTAsCreateMixin` for the DRF viewset |

### Request flow

- HTTP is served via **Daphne** (ASGI). The ASGI entrypoint (`treasure/asgi.py`) routes HTTP to Django and WebSocket connections to the Channels `ChatConsumer`.
- Player access is gated by `@login_required` and the `@no_players_during_lockout` decorator, which blocks players during UK working hours and before a configured start time.
- Staff users bypass lockout and see all levels.

### Settings

`treasure/settings.py` switches between `LOCAL` and `AZURE` deployment via the `DEPLOYMENT` env var. Local uses SQLite + in-memory channel layer; Azure uses MSSQL + Redis pub/sub channel layer + Azure Blob Storage.

`treasure/test_settings.py` imports from `settings.py` and overrides: MD5 password hasher (for speed), `InMemoryStorage`, removes WhiteNoise middleware.

## Testing

Tests live in `hunt/tests/` and use **pytest-django**. The settings module for tests is `treasure.test_settings` (configured in `pyproject.toml` under `[tool.pytest]`).

Fixtures are in `hunt/tests/conftest.py` — key fixtures include `user`, `staff_user`, `create_user` (factory), `level`, `create_level` (factory), `level_with_hints`, and `app_setting`. Use the `make_request()` helper to create `AuthenticatedHttpRequest` objects with `RequestFactory`.

## Code Conventions

- **`from __future__ import annotations`** is required in every Python file (enforced by ruff isort `required-imports`).
- **Ruff** is the linter and formatter with `select = ["ALL"]` and specific ignores. Relative imports are banned (`ban-relative-imports = "all"`).
- **mypy** runs in strict mode with `django-stubs`, `djangorestframework-stubs`, and `pydantic` plugins.
- `hunt/migrations/` is excluded from ruff.
- Views are function-based; the REST API uses DRF class-based viewsets.
- `AppSetting` is a singleton model — its `save()` deletes all other instances.
- `HuntInfo` is auto-created via a `post_save` signal when a `User` is created.
