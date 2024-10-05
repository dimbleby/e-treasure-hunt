"""Functions for requesting hints."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django.utils import timezone

from hunt.constants import HINTS_PER_LEVEL
from hunt.models import HuntEvent, HuntInfo
from hunt.utils import max_level

if TYPE_CHECKING:
    from django.contrib.auth.models import User

    from hunt.utils import AuthenticatedHttpRequest


def request_hint(request: AuthenticatedHttpRequest) -> str:
    hunt_info = request.user.huntinfo

    # Check that this is a request for the user's current level.
    lvl = request.GET.get("lvl")
    if lvl is None:
        return "/oops"

    if int(lvl) != hunt_info.level:
        return "/oops"

    # Check that this request is for the expected hint.
    hint = request.GET.get("hint")
    if hint is None:
        return "/oops"

    if int(hint) != hunt_info.hints_shown:
        return "/level/" + lvl

    # Prevent requesting more hints than there are.
    if hunt_info.hints_shown >= HINTS_PER_LEVEL:
        return "/oops"

    # If a hint request is already in progress, there's nothing to do here.
    # Just send the user back to the level they're on.
    if hunt_info.hint_requested:
        return "/level/" + lvl

    # Log an event to say there's been a hint request.
    event = HuntEvent()
    event.time = timezone.now()
    event.kind = HuntEvent.HINT_REQ
    event.user = request.user
    event.level = hunt_info.level
    event.save()

    # Record that a hint has been requested.
    hunt_info.hint_requested = True
    hunt_info.save()

    # Redirect back to the level in question.
    return "/level/" + lvl


def determine_hint_delay(hunt_info: HuntInfo) -> timedelta:
    """Determine how long a user has to wait before seeing the next hint."""

    # Figure out where everyone stands.
    hunts = HuntInfo.objects.filter(user__is_staff=False).order_by(
        "-level", "-hints_shown"
    )
    places = [(h.level, h.hints_shown) for h in hunts]
    user_place = (hunt_info.level, hunt_info.hints_shown)

    # Default to a 30 minute delay and tweak according to the user's place.
    #
    # If everyone is in the same place, no tweaks.
    #
    # Leaders are delayed by an additional ten minutes.
    #
    # Last place gets a ten minute reduction.
    delay = 30
    if places[0] == places[-1]:
        pass

    elif user_place == places[0]:
        delay += 10

    elif user_place == places[-1]:
        delay -= 10

    return timedelta(minutes=delay)


def prepare_next_hint(hunt_info: HuntInfo) -> None:
    """Prepare to release the next hint, by calculating when it becomes available."""
    # Don't try to release more hints than there are.
    if hunt_info.hints_shown >= HINTS_PER_LEVEL:
        return

    # Don't try to release hints on the last level.
    if hunt_info.level >= max_level():
        return

    # Calculate when to release the next hint.
    now = timezone.now()
    delay = determine_hint_delay(hunt_info)
    hunt_info.next_hint_release = now + delay
    hunt_info.save()


def maybe_release_hint(user: User) -> None:
    """Release any requested hint that has become available."""
    hunt_info = user.huntinfo

    if not hunt_info.hint_requested:
        return

    if hunt_info.next_hint_release is None:
        return

    now = timezone.now()
    if now < hunt_info.next_hint_release:
        return

    # Record the event.
    event = HuntEvent()
    event.time = now
    event.user = user
    event.kind = HuntEvent.HINT_REL
    event.level = hunt_info.level
    event.save()

    # Release this hint.
    hunt_info.hints_shown += 1
    hunt_info.hint_requested = False
    hunt_info.next_hint_release = None
    hunt_info.save()
