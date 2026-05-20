"""Pytest fixtures for hunt app tests."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from django.contrib.auth.models import User
from django.test import RequestFactory

from hunt.models import AppSetting, Level

if TYPE_CHECKING:
    from collections.abc import Callable

    from hunt.utils import AuthenticatedHttpRequest


@pytest.fixture(autouse=True)
def _disable_lockout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable the lockout decorator by default.

    The real ``players_are_locked_out`` consults the wall clock and returns
    ``True`` during configured work hours, which makes view tests depend on
    the time of day. Tests that want to exercise lockout behaviour patch
    this name explicitly with ``unittest.mock.patch(...)``; that patch will
    take precedence over this fixture for the duration of its ``with``
    block.
    """
    monkeypatch.setattr("hunt.utils.players_are_locked_out", lambda: False)


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
def app_setting(db: None) -> AppSetting:
    """Create an app setting."""
    _ = db

    return AppSetting.objects.create(active=True, use_alternative_map=False)
