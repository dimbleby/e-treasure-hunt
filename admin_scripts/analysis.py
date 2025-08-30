#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime
import zoneinfo
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import dateutil.parser
import matplotlib.pyplot as plt

LEVELS = 38


class EventType(Enum):
    REQUEST = "REQ"
    RELEASE = "REL"
    ADVANCE = "ADV"


class Team(Enum):
    RED = "lannister"
    BLUE = "stark"
    YELLOW = "baratheon"
    GREEN = "targaryen"


COLORS = {
    Team.RED: "red",
    Team.BLUE: "blue",
    Team.YELLOW: "yellow",
    Team.GREEN: "green",
}


@dataclass
class Event:
    identity: int
    time: datetime.datetime
    kind: EventType
    team: Team
    level: int

    @classmethod
    def from_row(cls, row: dict[str, str]) -> Event:
        id_ = int(row["id"])
        time = dateutil.parser.parse(row["time"])
        kind = EventType(row["kind"])
        team = Team(row["user"])
        level = int(row["level"])
        return cls(id_, time, kind, team, level)


def parse(filename: Path) -> list[Event]:
    with filename.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [Event.from_row(row) for row in reader]


def team_advance_times(events: list[Event]) -> dict[Team, list[float]]:
    """
    Returns a dictionary keyed by team, with items being a list of the times, in hours,
    at which the team advanced to each level.
    """
    london = zoneinfo.ZoneInfo("Europe/London")
    start = datetime.datetime(2024, 7, 10, 12, 30, tzinfo=london)
    advances = [event for event in events if event.kind is EventType.ADVANCE]
    return {
        team: [
            (event.time - start).total_seconds() / 3600
            for event in advances
            if event.team is team
        ]
        for team in Team
    }


def team_hints(events: list[Event]) -> dict[Team, Counter[int]]:
    """
    Returns a dictionary keyed by team, with items being a count of the hints used at
    each level.
    """
    hints: dict[Team, Counter[int]] = {team: Counter() for team in Team}
    for event in events:
        if event.kind is EventType.REQUEST:
            hints[event.team][event.level] += 1

    return hints


def team_cumulative_hints(events: list[Event]) -> dict[Team, Counter[int]]:
    """
    Returns a dictionary keyed by team, with items being a cumulative count of the hints
    used at each level.
    """
    hints = team_hints(events)

    cumulative: dict[Team, Counter[int]] = {team: Counter({0: 0}) for team in Team}
    for team in Team:
        for level in range(1, LEVELS + 1):
            cumulative[team][level] = cumulative[team][level - 1] + hints[team][level]
    return cumulative


def team_solve_times(events: list[Event]) -> dict[Team, list[float]]:
    """
    Returns a dictionary keyed by team, with items being a list of solve times for each
    level, in hours.
    """
    times = team_advance_times(events)

    for line in times.values():
        line.insert(0, 0)

    return {
        team: [x - y for x, y in zip(line[1:], line, strict=False)]
        for team, line in times.items()
    }


def time_race(events: list[Event]) -> None:
    """
    Draw the 'Roadrunner' graph.
    """
    times = team_advance_times(events)

    # Sort by the time of the final event.
    times = dict(sorted(times.items(), key=lambda item: item[1][-1]))
    for team, line in times.items():
        line.insert(0, 0)
        plt.plot(line, range(len(line)), label=team.value, color=COLORS[team])
    plt.legend()
    plt.grid(axis="both")
    plt.xlabel("Hour at which level was solved")
    plt.ylabel("Level")
    plt.title("Roadrunner")
    plt.savefig("Roadrunner", dpi=200)
    # plt.show()
    plt.clf()


def hint_race(events: list[Event]) -> None:
    """
    Draw the 'Sherlock' graph.
    """
    cumulative = team_cumulative_hints(events)

    # Sort by the final number of hints used.
    cumulative = dict(
        sorted(cumulative.items(), key=lambda item: item[1][LEVELS], reverse=True)
    )
    for team, counter in cumulative.items():
        plt.plot(
            list(counter.keys()),
            list(counter.values()),
            label=team.value,
            color=COLORS[team],
        )

    plt.legend()
    plt.grid(axis="both")
    plt.xlabel("Level")
    plt.ylabel("Cumulative hints requested")
    plt.title("Sherlock")
    plt.savefig("Sherlock", dpi=200)
    # plt.show()
    plt.clf()


def combined_race(events: list[Event], penalty: float = 1.0) -> None:
    """
    Draw the 'All-rounder' graph.
    """
    cumulative = team_cumulative_hints(events)
    times = team_advance_times(events)
    combined = {
        team: [
            time + penalty * cumulative[team][level]
            for level, time in enumerate(times[team], 1)
        ]
        for team in Team
    }

    # Sort by the time of the final event.
    combined = dict(sorted(combined.items(), key=lambda item: item[1][-1]))
    for team, line in combined.items():
        line.insert(0, 0)
        plt.plot(line, range(len(line)), label=team.value, color=COLORS[team])
    plt.legend()
    plt.grid(axis="both")
    plt.xlabel("Hour at which level was solved, with penalties")
    plt.ylabel("Level")
    plt.title(f"All-rounder ({penalty:.1f} hour penalty)")
    plt.savefig(f"All-rounder-{penalty:.1f}.png", dpi=200)
    # plt.show()
    plt.clf()


def hints_per_level(events: list[Event]) -> None:
    """
    Draw a graph showing the number of hints requested on each level.
    """
    hints = team_hints(events)

    # Reverse the order so that alphabetically first teams are at the top.
    hints = dict(sorted(hints.items(), key=lambda item: item[0].name, reverse=True))

    # Need to keep track of the running total so that we can stack the bars.
    total: Counter[int] = Counter()
    ax = plt.subplot(1, 1, 1)
    for team, counter in hints.items():
        ax.bar(
            list(counter),
            list(counter.values()),
            label=team.value,
            color=COLORS[team],
            bottom=[total[key] for key in counter],
        )
        total += counter
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(list(reversed(handles)), list(reversed(labels)))
    plt.xticks(range(5, LEVELS + 1, 5))
    ax.grid(axis="y")
    axes = plt.gca()
    axes.set_ylim(0, 16)
    plt.xlabel("Level")
    plt.ylabel("No of Hints")
    plt.title("Hints requested per level (all teams)")
    plt.savefig("Hints-per-level", dpi=200)
    # plt.show()
    plt.clf()


def time_per_level(events: list[Event]) -> None:
    """
    Draw a graph showing the amount of time taken on each level.
    """
    times = team_solve_times(events)

    # Reverse the order so that alphabetically first teams are at the top.
    times = dict(sorted(times.items(), key=lambda item: item[0].name, reverse=True))

    # Need to keep track of the running total so that we can stack the bars.
    total = [0.0 for _ in range(LEVELS + 1)]
    ax = plt.subplot(1, 1, 1)
    for team, line in times.items():
        line.insert(0, 0)
        ax.bar(
            range(len(line)),
            line,
            label=team.value,
            color=COLORS[team],
            bottom=total[: len(line)],
        )
        for idx, value in enumerate(line):
            total[idx] += value
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(list(reversed(handles)), list(reversed(labels)))
    plt.xticks(range(5, LEVELS + 1, 5))
    ax.grid(axis="y")
    plt.xlabel("Level")
    plt.ylabel("Hours")
    plt.title("Elapsed time per level (all teams)")
    plt.savefig("Time-per-level", dpi=200)
    # plt.show()
    plt.clf()


if __name__ == "__main__":
    csv_file = Path("hunt.huntevent.csv")
    events = parse(csv_file)

    time_race(events)

    hint_race(events)

    combined_race(events, penalty=1.0)
    combined_race(events, penalty=2.0)
    combined_race(events, penalty=3.0)

    hints_per_level(events)

    time_per_level(events)

    solve_times = team_solve_times(events)
    print("Fastest solves:")
    for team, line in solve_times.items():
        (time, level) = min((val, idx) for idx, val in enumerate(line, 1))
        print(f"{team.value}: level {level} took {int(3600 * time)}s")
