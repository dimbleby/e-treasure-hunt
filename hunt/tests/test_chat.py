"""Tests for chat WebSocket consumers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from asgiref.sync import sync_to_async

from hunt.chat.consumers import async_get_level, async_is_level_allowed
from hunt.models import Level

if TYPE_CHECKING:
    from django.contrib.auth.models import User


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestAsyncIsLevelAllowed:
    """Tests for async_is_level_allowed function."""

    async def test_level_zero_not_allowed(self, user: User) -> None:
        """Level 0 should not be allowed for any user."""
        result = await async_is_level_allowed(user, 0)
        assert result is False

    async def test_negative_level_not_allowed(self, user: User) -> None:
        """Negative levels should not be allowed."""
        result = await async_is_level_allowed(user, -1)
        assert result is False

    async def test_staff_allowed_any_level(self, staff_user: User) -> None:
        """Staff should be allowed to access any level."""
        result = await async_is_level_allowed(staff_user, 100)
        assert result is True

    async def test_user_allowed_current_level(self, user: User) -> None:
        """User should be allowed to access their current level."""
        # User starts at level 1
        result = await async_is_level_allowed(user, 1)
        assert result is True

    async def test_user_not_allowed_future_level(self, user: User) -> None:
        """User should not be allowed to access future levels."""
        # User is at level 1, should not access level 2
        result = await async_is_level_allowed(user, 2)
        assert result is False

    async def test_user_allowed_past_level(self, user: User) -> None:
        """User should be allowed to access past levels."""
        user.huntinfo.level = 3
        await user.huntinfo.asave()

        result = await async_is_level_allowed(user, 2)
        assert result is True


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestAsyncGetLevel:
    """Tests for async_get_level function."""

    async def test_get_existing_level(self) -> None:
        """Should return the level with the given number."""

        @sync_to_async
        def create_level() -> Level:
            return Level.objects.create(
                number=1,
                name="Test Level",
                latitude="51.50722",
                longitude="-0.12750",
                tolerance=50,
            )

        await create_level()

        level = await async_get_level(1)
        assert level.number == 1
        assert level.name == "Test Level"

    async def test_get_nonexistent_level_raises(self) -> None:
        """Should raise DoesNotExist for nonexistent level."""
        with pytest.raises(Level.DoesNotExist):
            await async_get_level(999)
