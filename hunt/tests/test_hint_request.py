"""Tests for hint request functionality."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django.utils import timezone

from hunt.hint_request import (
    determine_hint_delay,
    maybe_release_hint,
    prepare_next_hint,
    request_hint,
)
from hunt.models import HuntEvent
from hunt.tests.conftest import make_request

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.contrib.auth.models import User

    from hunt.models import Level


class TestRequestHint:
    """Tests for request_hint function."""

    def test_request_hint_without_level_param(self, user: User) -> None:
        """request_hint should redirect to oops if level param is missing."""
        request = make_request("/hint", user=user)

        result = request_hint(request)
        assert result["Location"] == "/oops"

    def test_request_hint_with_invalid_level(self, user: User) -> None:
        """request_hint should redirect to oops if level is not an integer."""
        request = make_request("/hint", user=user, data={"lvl": "abc"})

        result = request_hint(request)
        assert result["Location"] == "/oops"

    def test_request_hint_for_wrong_level(self, user: User) -> None:
        """request_hint should redirect to oops if not user's current level."""
        user.huntinfo.level = 2
        user.huntinfo.save()

        request = make_request("/hint", user=user, data={"lvl": "1", "hint": "1"})

        result = request_hint(request)
        assert result["Location"] == "/oops"

    def test_request_hint_without_hint_param(self, user: User) -> None:
        """request_hint should redirect to oops if hint param is missing."""
        request = make_request("/hint", user=user, data={"lvl": "1"})

        result = request_hint(request)
        assert result["Location"] == "/oops"

    def test_request_hint_for_wrong_hint_number(self, user: User) -> None:
        """request_hint should redirect to level if wrong hint number."""
        request = make_request("/hint", user=user, data={"lvl": "1", "hint": "2"})

        result = request_hint(request)
        assert result["Location"] == "/level/1"

    def test_request_hint_already_requested(self, user: User) -> None:
        """request_hint should redirect to level if hint already requested."""
        user.huntinfo.hint_requested = True
        user.huntinfo.save()

        request = make_request("/hint", user=user, data={"lvl": "1", "hint": "1"})

        result = request_hint(request)
        assert result["Location"] == "/level/1"

    def test_request_hint_success(self, user: User) -> None:
        """request_hint should set hint_requested and create event."""
        request = make_request("/hint", user=user, data={"lvl": "1", "hint": "1"})

        result = request_hint(request)

        user.huntinfo.refresh_from_db()
        assert user.huntinfo.hint_requested is True
        assert HuntEvent.objects.filter(kind=HuntEvent.EventKind.HINT_REQ).exists()
        assert result["Location"] == "/level/1"


class TestDetermineHintDelay:
    """Tests for determine_hint_delay function."""

    def test_default_delay(self, user: User) -> None:
        """Default delay should be 30 minutes when everyone is equal."""
        delay = determine_hint_delay(user.huntinfo)
        assert delay == timedelta(minutes=30)

    def test_leader_gets_extra_delay(self, create_user: Callable[..., User]) -> None:
        """Leader should get 10 extra minutes delay."""
        leader = create_user(username="leader")
        leader.huntinfo.level = 2
        leader.huntinfo.save()

        create_user(username="follower")  # stays at level 1

        delay = determine_hint_delay(leader.huntinfo)
        assert delay == timedelta(minutes=40)

    def test_last_place_gets_reduced_delay(
        self, create_user: Callable[..., User]
    ) -> None:
        """Last place should get 10 minutes less delay."""
        leader = create_user(username="leader")
        leader.huntinfo.level = 2
        leader.huntinfo.save()

        follower = create_user(username="follower")
        # follower stays at level 1 (last place)

        delay = determine_hint_delay(follower.huntinfo)
        assert delay == timedelta(minutes=20)


class TestPrepareNextHint:
    """Tests for prepare_next_hint function."""

    def test_prepare_next_hint_sets_release_time(
        self, user: User, create_level: Callable[..., Level]
    ) -> None:
        """prepare_next_hint should set the next_hint_release time."""
        create_level(number=1)
        create_level(number=2)

        prepare_next_hint(user.huntinfo)

        user.huntinfo.refresh_from_db()
        assert user.huntinfo.next_hint_release is not None

    def test_prepare_next_hint_skipped_at_max_hints(
        self, user: User, create_level: Callable[..., Level]
    ) -> None:
        """prepare_next_hint should not set time if max hints shown."""
        create_level(number=1)
        create_level(number=2)

        user.huntinfo.hints_shown = 5  # Max hints
        user.huntinfo.save()

        prepare_next_hint(user.huntinfo)

        user.huntinfo.refresh_from_db()
        assert user.huntinfo.next_hint_release is None

    def test_prepare_next_hint_skipped_at_last_level(
        self, user: User, create_level: Callable[..., Level]
    ) -> None:
        """prepare_next_hint should not set time on the last level."""
        create_level(number=1)
        # user.huntinfo.level is 1, which is also max_level

        prepare_next_hint(user.huntinfo)

        user.huntinfo.refresh_from_db()
        assert user.huntinfo.next_hint_release is None


class TestMaybeReleaseHint:
    """Tests for maybe_release_hint function."""

    def test_no_release_if_not_requested(self, user: User) -> None:
        """Hint should not be released if not requested."""
        user.huntinfo.next_hint_release = timezone.now() - timedelta(minutes=1)
        user.huntinfo.save()

        maybe_release_hint(user)

        user.huntinfo.refresh_from_db()
        assert user.huntinfo.hints_shown == 1

    def test_no_release_if_no_release_time(self, user: User) -> None:
        """Hint should not be released if no release time set."""
        user.huntinfo.hint_requested = True
        user.huntinfo.save()

        maybe_release_hint(user)

        user.huntinfo.refresh_from_db()
        assert user.huntinfo.hints_shown == 1

    def test_no_release_if_not_time_yet(self, user: User) -> None:
        """Hint should not be released if release time is in future."""
        user.huntinfo.hint_requested = True
        user.huntinfo.next_hint_release = timezone.now() + timedelta(minutes=10)
        user.huntinfo.save()

        maybe_release_hint(user)

        user.huntinfo.refresh_from_db()
        assert user.huntinfo.hints_shown == 1

    def test_release_hint_when_time(self, user: User) -> None:
        """Hint should be released when time has passed."""
        user.huntinfo.hint_requested = True
        user.huntinfo.next_hint_release = timezone.now() - timedelta(minutes=1)
        user.huntinfo.save()

        maybe_release_hint(user)

        user.huntinfo.refresh_from_db()
        assert user.huntinfo.hints_shown == 2
        assert user.huntinfo.hint_requested is False
        assert HuntEvent.objects.filter(kind=HuntEvent.EventKind.HINT_REL).exists()
        assert user.huntinfo.next_hint_release is None
