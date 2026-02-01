"""Pytest fixtures for hunt app tests."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import RequestFactory
from django.utils import timezone

from hunt.models import AppSetting, Hint, Level

if TYPE_CHECKING:
    from collections.abc import Callable

    from hunt.utils import AuthenticatedHttpRequest


def make_request(
    path: str,
    user: User,
    *,
    data: dict[str, str] | None = None,
) -> AuthenticatedHttpRequest:
    """Create an AuthenticatedHttpRequest."""

    factory = RequestFactory()
    request = factory.get(path, data)
    request.user = user

    return request  # type: ignore[return-value]


@pytest.fixture
def create_user(db: None) -> Callable[..., User]:
    """Factory fixture to create users."""
    _ = db

    def _create_user(
        username: str = "testuser",
        password: str = "testpass123",  # noqa: S107
        *,
        is_staff: bool = False,
    ) -> User:
        return User.objects.create_user(
            username=username, password=password, is_staff=is_staff
        )

    return _create_user


@pytest.fixture
def user(create_user: Callable[..., User]) -> User:
    """Create a regular user."""
    return create_user()


@pytest.fixture
def staff_user(create_user: Callable[..., User]) -> User:
    """Create a staff user."""
    return create_user(username="staffuser", is_staff=True)


@pytest.fixture
def create_level(db: None) -> Callable[..., Level]:
    """Factory fixture to create levels."""
    _ = db

    def _create_level(
        number: int = 1,
        name: str = "Test Level",
        description: str = "Test description",
        latitude: Decimal = Decimal("51.50722"),
        longitude: Decimal = Decimal("-0.12750"),
        tolerance: int = 50,
    ) -> Level:
        return Level.objects.create(
            number=number,
            name=name,
            description=description,
            latitude=latitude,
            longitude=longitude,
            tolerance=tolerance,
        )

    return _create_level


@pytest.fixture
def level(create_level: Callable[..., Level]) -> Level:
    """Create a default test level."""
    return create_level()


@pytest.fixture
def level_with_hints(level: Level) -> Level:
    """Create a level with hints."""
    for i in range(5):
        hint = Hint(level=level, number=i)
        hint.image.save(f"hint_{i}.jpg", ContentFile(b"fake image content"))
    return level


@pytest.fixture
def app_setting(db: None) -> AppSetting:
    """Create an app setting."""
    _ = db

    return AppSetting.objects.create(active=True, use_alternative_map=False)


@pytest.fixture
def app_setting_with_start_time(db: None) -> AppSetting:
    """Create an app setting with a start time in the past."""
    _ = db

    return AppSetting.objects.create(
        active=True,
        use_alternative_map=False,
        start_time=timezone.now() - timedelta(hours=1),
    )
