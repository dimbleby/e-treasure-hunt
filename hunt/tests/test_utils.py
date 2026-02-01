"""Tests for hunt utility functions."""

from __future__ import annotations

import datetime
import zoneinfo
from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from django.utils import timezone

from hunt.models import AppSetting
from hunt.utils import max_level, players_are_locked_out

if TYPE_CHECKING:
    from collections.abc import Callable

    from hunt.models import Level


class TestMaxLevel:
    """Tests for max_level function."""

    def test_max_level_single_level(self, level: Level) -> None:
        """max_level should return the highest level number."""
        _ = level  # Fixture creates level in database
        assert max_level() == 1

    def test_max_level_multiple_levels(
        self, create_level: Callable[..., Level]
    ) -> None:
        """max_level should return the highest level number with multiple levels."""
        create_level(number=1)
        create_level(number=2, name="Level 2")
        create_level(number=5, name="Level 5")
        assert max_level() == 5


@pytest.mark.django_db
class TestPlayersLockedOut:
    """Tests for players_are_locked_out function."""

    def test_locked_out_before_start_time(self) -> None:
        """Players should be locked out before the configured start time."""
        future_start = timezone.now() + timedelta(hours=1)
        AppSetting.objects.create(active=True, start_time=future_start)
        assert players_are_locked_out() is True

    def test_not_locked_out_after_start_time(self) -> None:
        """Players should not be locked out on weekend after start time."""
        # Mock a weekend time - no work hours check applies
        london = zoneinfo.ZoneInfo("Europe/London")
        saturday = datetime.datetime(2024, 1, 6, 10, 0, tzinfo=london)  # Saturday
        past_start = saturday - timedelta(hours=1)
        AppSetting.objects.create(active=True, start_time=past_start)

        with patch("hunt.utils.datetime") as mock_datetime:
            mock_datetime.datetime.now.return_value = saturday
            mock_datetime.time = datetime.time
            assert players_are_locked_out() is False

    def test_not_locked_out_on_weekend(self) -> None:
        """Players should not be locked out on weekends."""
        london = zoneinfo.ZoneInfo("Europe/London")
        saturday = datetime.datetime(2024, 1, 6, 10, 0, tzinfo=london)  # Saturday

        with patch("hunt.utils.datetime") as mock_datetime:
            mock_datetime.datetime.now.return_value = saturday
            mock_datetime.time = datetime.time
            assert players_are_locked_out() is False

    def test_locked_out_during_morning_work_hours(self) -> None:
        """Players should be locked out during morning work hours."""
        london = zoneinfo.ZoneInfo("Europe/London")
        # Tuesday at 10:00 AM
        work_time = datetime.datetime(2024, 1, 2, 10, 0, tzinfo=london)

        with (
            patch("hunt.utils.datetime") as mock_datetime,
            patch("hunt.utils.holidays.country_holidays") as mock_holidays,
        ):
            mock_datetime.datetime.now.return_value = work_time
            mock_datetime.time = datetime.time
            mock_holidays.return_value = set()  # No holidays
            assert players_are_locked_out() is True

    def test_locked_out_during_afternoon_work_hours(self) -> None:
        """Players should be locked out during afternoon work hours."""
        london = zoneinfo.ZoneInfo("Europe/London")
        # Tuesday at 2:00 PM
        work_time = datetime.datetime(2024, 1, 2, 14, 0, tzinfo=london)

        with (
            patch("hunt.utils.datetime") as mock_datetime,
            patch("hunt.utils.holidays.country_holidays") as mock_holidays,
        ):
            mock_datetime.datetime.now.return_value = work_time
            mock_datetime.time = datetime.time
            mock_holidays.return_value = set()  # No holidays
            assert players_are_locked_out() is True

    def test_not_locked_out_during_lunch(self) -> None:
        """Players should not be locked out during lunch time."""
        london = zoneinfo.ZoneInfo("Europe/London")
        # Tuesday at 1:00 PM (lunch)
        lunch_time = datetime.datetime(2024, 1, 2, 13, 0, tzinfo=london)

        with (
            patch("hunt.utils.datetime") as mock_datetime,
            patch("hunt.utils.holidays.country_holidays") as mock_holidays,
        ):
            mock_datetime.datetime.now.return_value = lunch_time
            mock_datetime.time = datetime.time
            mock_holidays.return_value = set()  # No holidays
            assert players_are_locked_out() is False

    def test_not_locked_out_on_bank_holiday(self) -> None:
        """Players should not be locked out on bank holidays."""
        london = zoneinfo.ZoneInfo("Europe/London")
        # A weekday during work hours
        holiday_time = datetime.datetime(2024, 1, 1, 10, 0, tzinfo=london)

        with (
            patch("hunt.utils.datetime") as mock_datetime,
            patch("hunt.utils.holidays.country_holidays") as mock_holidays,
        ):
            mock_datetime.datetime.now.return_value = holiday_time
            mock_datetime.time = datetime.time
            # Jan 1st is a holiday
            mock_holidays.return_value = {holiday_time.date()}
            assert players_are_locked_out() is False
