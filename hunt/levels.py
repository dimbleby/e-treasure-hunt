from __future__ import annotations

from typing import TYPE_CHECKING

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from geopy import Point, distance

from hunt.constants import HINTS_PER_LEVEL
from hunt.models import ChatMessage, HuntEvent, Level
from hunt.utils import get_int_param, max_level

if TYPE_CHECKING:
    from django.contrib.auth.models import User
    from django.http import HttpResponse

    from hunt.utils import AuthenticatedHttpRequest


def advance_level(user: User) -> None:
    hunt_info = user.huntinfo
    new_level = hunt_info.level + 1

    # Log an event to record this.
    HuntEvent.objects.create(
        time=timezone.now(),
        kind=HuntEvent.EventKind.CLUE_ADV,
        user=user,
        level=new_level,
    )

    # Update the team's level, clear any hint request flags and save.
    hunt_info.level = new_level
    hunt_info.hints_shown = 1
    hunt_info.hint_requested = False
    hunt_info.next_hint_release = None
    hunt_info.save()


def look_for_level(request: AuthenticatedHttpRequest) -> HttpResponse:
    # Get latitude and longitude - without these there can be no searching.
    latitude = request.GET.get("lat")
    longitude = request.GET.get("long")
    if latitude is None or longitude is None:
        return HttpResponseRedirect(reverse("search"))

    # Every search must be for a specific level - by default, assume this is the team's
    # current level.
    user = request.user
    team_level = max_level() if user.is_staff else user.huntinfo.level
    search_level = get_int_param(request, "lvl") or team_level

    # Prevent searching for later levels.
    if search_level > team_level:
        return HttpResponseRedirect(reverse("oops"))

    # Make sure we're searching in a valid place.
    try:
        search_point = Point(latitude, longitude)
    except ValueError:
        return HttpResponseRedirect(reverse("oops"))

    # Get the distance between the search location and the level solution.
    level = Level.objects.get(number=search_level)
    level_point = Point(level.latitude, level.longitude)
    dist = distance.distance(search_point, level_point).m

    # If the distance is small enough, accept the solution.
    if dist <= level.tolerance:
        if search_level == team_level:
            advance_level(user)

        # Redirect to the new level.
        return HttpResponseRedirect(reverse("level", args=[search_level + 1]))

    # Redirect to a failure page.
    return HttpResponseRedirect(f"{reverse('nothing-here')}?lvl={search_level}")


def maybe_load_level(request: AuthenticatedHttpRequest, level_num: int) -> HttpResponse:
    # Get the user details.
    user = request.user
    team = user.huntinfo

    # Find the last level.  Staff can see everything.
    max_level_num = max_level()
    team_level = max_level_num if user.is_staff else team.level

    # Only load the level if it's one the team has access to.
    if 0 < level_num <= team_level:
        # Get this level and the one before.
        levels_dict = {
            lvl.number: lvl
            for lvl in Level.objects.filter(number__in=[level_num, level_num - 1])
        }
        current_level = levels_dict[level_num]
        previous_level = levels_dict[level_num - 1]

        # Decide how many images to display.  Show all hints for solved levels.
        num_hints = HINTS_PER_LEVEL if level_num < team_level else team.hints_shown

        # Get the URLs for the images to show.
        hints = current_level.hints.filter(number__lt=num_hints).order_by("number")
        hint_urls = [hint.image.url for hint in hints]

        # Don't allow a hint if one has already been requested by the team, or if max
        # hints are already shown.
        if team.hint_requested:
            allow_hint = False
            reason = "Your team has already requested a hint."
        elif team.hints_shown >= HINTS_PER_LEVEL:
            allow_hint = False
            reason = "No more hints are available on this level."
        else:
            allow_hint = True
            reason = ""

        is_last_level = current_level.number == max_level_num
        desc_paras = previous_level.description.splitlines()

        template = "level.html"
        context = {
            "team_level": team_level,
            "level_number": current_level.number,
            "level_name": previous_level.name.upper(),
            "hints": hint_urls,
            "desc_paras": desc_paras,
            "allow_hint": allow_hint,
            "reason": reason,
            "latitude": previous_level.latitude,
            "longitude": previous_level.longitude,
            "is_last": is_last_level,
            "messages": ChatMessage.objects.filter(team=user, level=current_level),
        }
    else:
        # Shouldn't be here. Show an error page.
        template = "oops.html"
        context = {"team_level": team_level}

    return render(request, template, context)


def list_levels(request: AuthenticatedHttpRequest) -> HttpResponse:
    # Get the team's current level.  Staff can see all levels.
    user = request.user
    team_level = max_level() if user.is_staff else user.huntinfo.level

    def truncate(name: str) -> str:
        if len(name) > 20:
            return name[:20] + "..."
        return name

    done_levels = Level.objects.filter(number__gt=0, number__lt=team_level).order_by(
        "number"
    )
    levels = [
        {"number": level.number, "name": truncate(level.name)} for level in done_levels
    ]
    levels.append({"number": team_level, "name": "Latest level"})

    context = {"team_level": team_level, "levels": levels}
    return render(request, "levels.html", context)
