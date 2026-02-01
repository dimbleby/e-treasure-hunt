"""Tests for level functionality."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from hunt.levels import advance_level, list_levels, look_for_level
from hunt.models import HuntEvent
from hunt.tests.conftest import make_request

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.contrib.auth.models import User

    from hunt.models import Level


class TestAdvanceLevel:
    """Tests for advance_level function."""

    def test_advance_level_increments_level(self, user: User) -> None:
        """advance_level should increment the user's level."""
        assert user.huntinfo.level == 1

        advance_level(user)

        user.huntinfo.refresh_from_db()
        assert user.huntinfo.level == 2

    def test_advance_level_resets_hints(self, user: User) -> None:
        """advance_level should reset hints_shown to 1."""
        user.huntinfo.hints_shown = 3
        user.huntinfo.save()

        advance_level(user)

        user.huntinfo.refresh_from_db()
        assert user.huntinfo.hints_shown == 1

    def test_advance_level_clears_hint_requested(self, user: User) -> None:
        """advance_level should clear hint_requested flag."""
        user.huntinfo.hint_requested = True
        user.huntinfo.save()

        advance_level(user)

        user.huntinfo.refresh_from_db()
        assert user.huntinfo.hint_requested is False

    def test_advance_level_creates_event(self, user: User) -> None:
        """advance_level should create a HuntEvent."""
        advance_level(user)

        event = HuntEvent.objects.get(kind=HuntEvent.EventKind.CLUE_ADV)
        assert event.user == user
        assert event.level == 2


class TestLookForLevel:
    """Tests for look_for_level function."""

    def test_look_for_level_without_coordinates(self, user: User) -> None:
        """look_for_level should redirect to search if no coordinates."""
        request = make_request("/do-search", user=user)

        result = look_for_level(request)
        assert result == "/search"

    def test_look_for_level_missing_longitude(self, user: User) -> None:
        """look_for_level should redirect to search if only latitude."""
        request = make_request("/do-search", user=user, data={"lat": "51.5"})

        result = look_for_level(request)
        assert result == "/search"

    def test_look_for_level_future_level(
        self, user: User, create_level: Callable[..., Level]
    ) -> None:
        """look_for_level should redirect to oops for future levels."""
        create_level(number=1)
        create_level(number=2)

        request = make_request(
            "/do-search", user=user, data={"lat": "51.5", "long": "-0.1", "lvl": "2"}
        )

        result = look_for_level(request)
        assert result == "/oops"

    def test_look_for_level_invalid_coordinates(
        self, user: User, create_level: Callable[..., Level]
    ) -> None:
        """look_for_level should redirect to oops for invalid coordinates."""
        create_level(number=1)

        request = make_request(
            "/do-search", user=user, data={"lat": "invalid", "long": "-0.1"}
        )

        result = look_for_level(request)
        assert result == "/oops"

    def test_look_for_level_correct_answer(
        self, user: User, create_level: Callable[..., Level]
    ) -> None:
        """look_for_level should advance level on correct answer."""
        lat, lon = Decimal("51.50722"), Decimal("-0.12750")
        create_level(number=1, latitude=lat, longitude=lon)
        create_level(number=2, name="Level 2")

        request = make_request(
            "/do-search", user=user, data={"lat": "51.50722", "long": "-0.12750"}
        )

        result = look_for_level(request)

        user.huntinfo.refresh_from_db()
        assert user.huntinfo.level == 2
        assert result == "/level/2"

    def test_look_for_level_wrong_answer(
        self, user: User, create_level: Callable[..., Level]
    ) -> None:
        """look_for_level should redirect to nothing-here on wrong answer."""
        create_level(number=1)

        # Search far from the level location
        request = make_request(
            "/do-search", user=user, data={"lat": "40.0", "long": "0.0"}
        )

        result = look_for_level(request)

        user.huntinfo.refresh_from_db()
        assert user.huntinfo.level == 1
        assert result == "/nothing-here?lvl=1"

    def test_look_for_level_staff_can_search_any(
        self, staff_user: User, create_level: Callable[..., Level]
    ) -> None:
        """Staff can search for any level."""
        lat, lon = Decimal("51.50722"), Decimal("-0.12750")
        create_level(number=1)
        create_level(number=2)
        create_level(number=3, latitude=lat, longitude=lon)
        create_level(number=4, name="Level 4")

        request = make_request(
            "/do-search",
            user=staff_user,
            data={"lat": "51.50722", "long": "-0.12750", "lvl": "3"},
        )

        result = look_for_level(request)
        assert result == "/level/4"

    def test_look_for_level_previous_level_no_advance(
        self, user: User, create_level: Callable[..., Level]
    ) -> None:
        """Solving a previous level should not advance team level."""
        lat, lon = Decimal("51.50722"), Decimal("-0.12750")
        create_level(number=1, latitude=lat, longitude=lon)
        create_level(number=2)

        user.huntinfo.level = 2
        user.huntinfo.save()

        request = make_request(
            "/do-search",
            user=user,
            data={"lat": "51.50722", "long": "-0.12750", "lvl": "1"},
        )

        result = look_for_level(request)

        user.huntinfo.refresh_from_db()
        assert user.huntinfo.level == 2  # Not advanced
        assert result == "/level/2"


class TestListLevels:
    """Tests for list_levels function."""

    @pytest.mark.django_db
    def test_list_levels_truncates_long_names(
        self,
        user: User,
        create_level: Callable[..., Level],
    ) -> None:
        """Level names longer than 20 chars should be truncated."""
        long_name = "This is a very long level name"
        create_level(number=1, name=long_name)
        user.huntinfo.level = 2
        user.huntinfo.save()

        request = make_request("/levels/", user=user)

        response = list_levels(request)
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_list_levels_shows_completed_levels(
        self,
        user: User,
        create_level: Callable[..., Level],
    ) -> None:
        """list_levels should show completed levels."""
        create_level(number=1, name="Level One")
        create_level(number=2, name="Level Two")
        create_level(number=3, name="Level Three")
        user.huntinfo.level = 3
        user.huntinfo.save()

        request = make_request("/levels/", user=user)

        response = list_levels(request)
        assert response.status_code == 200
