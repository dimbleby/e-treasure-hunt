"""Django settings for tests."""

from __future__ import annotations

from treasure.settings import *  # noqa: F403

# Use fast password hasher (default PBKDF2 is intentionally slow)
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Use simple storage backends.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Remove whitenoise middleware (requires static directory to exist)
MIDDLEWARE = [m for m in MIDDLEWARE if "whitenoise" not in m]  # noqa: F405
