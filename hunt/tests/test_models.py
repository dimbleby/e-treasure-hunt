"""Tests for hunt models."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import IntegrityError
from django.utils import timezone

from hunt.models import AppSetting, ChatMessage, Hint, HuntEvent, HuntInfo

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.contrib.auth.models import User

    from hunt.models import Level


class TestHuntInfo:
    """Tests for HuntInfo model."""

    def test_hunt_info_created_on_user_creation(self, user: User) -> None:
        """HuntInfo should be auto-created when a user is created."""
        assert hasattr(user, "huntinfo")
        assert isinstance(user.huntinfo, HuntInfo)

    def test_hunt_info_default_values(self, user: User) -> None:
        """HuntInfo should have correct default values."""
        hunt_info = user.huntinfo
        assert hunt_info.level == 1
        assert hunt_info.hints_shown == 1
        assert hunt_info.hint_requested is False
        assert hunt_info.next_hint_release is None

    def test_hunt_info_str(self, user: User) -> None:
        """HuntInfo string representation should be the username."""
        assert str(user.huntinfo) == user.get_username()


class TestLevel:
    """Tests for Level model."""

    def test_level_creation(self, level: Level) -> None:
        """Level should be created with correct values."""
        assert level.number == 1
        assert level.name == "Test Level"
        assert level.tolerance == 50

    def test_level_str(self, level: Level) -> None:
        """Level string representation."""
        assert str(level) == "Level 1"

    def test_level_latitude_validation(
        self, create_level: Callable[..., Level]
    ) -> None:
        """Level latitude should be between -90 and 90."""
        # Valid latitudes
        level = create_level(number=2, latitude=Decimal("90.00000"))
        assert level.latitude == Decimal("90.00000")

        level = create_level(number=3, latitude=Decimal("-90.00000"))
        assert level.latitude == Decimal("-90.00000")

    def test_level_longitude_validation(
        self, create_level: Callable[..., Level]
    ) -> None:
        """Level longitude should be between -180 and 180."""
        level = create_level(number=2, longitude=Decimal("180.00000"))
        assert level.longitude == Decimal("180.00000")

        level = create_level(number=3, longitude=Decimal("-180.00000"))
        assert level.longitude == Decimal("-180.00000")


class TestHint:
    """Tests for Hint model."""

    def test_hint_creation(self, level: Level) -> None:
        """Hint should be created with correct values."""
        hint = Hint.objects.create(level=level, number=0)
        hint.image.save("test.jpg", ContentFile(b"test"))
        assert hint.level == level
        assert hint.number == 0

    def test_hint_str(self, level: Level) -> None:
        """Hint string representation."""
        hint = Hint.objects.create(level=level, number=2)
        assert str(hint) == "Level 1, hint 2"

    def test_hint_unique_constraint(self, level: Level) -> None:
        """Only one hint per level/number combination."""
        Hint.objects.create(level=level, number=0)
        with pytest.raises(IntegrityError):
            Hint.objects.create(level=level, number=0)

    def test_hint_image_deleted_on_hint_delete(self, level: Level) -> None:
        """Hint image should be deleted when hint is deleted."""
        hint = Hint.objects.create(level=level, number=0)
        hint.image.save("test.jpg", ContentFile(b"test"))
        image_name = hint.image.name
        hint.delete()
        # The image should no longer exist
        assert not default_storage.exists(image_name)


class TestAppSetting:
    """Tests for AppSetting model."""

    def test_app_setting_creation(self, app_setting: AppSetting) -> None:
        """AppSetting should be created with correct values."""
        assert app_setting.active is True
        assert app_setting.use_alternative_map is False

    def test_app_setting_str(self, app_setting: AppSetting) -> None:
        """AppSetting string representation."""
        assert str(app_setting) == "App setting (active=True)"

    @pytest.mark.django_db
    def test_save_deletes_others_with_same_pk(self) -> None:
        """Saving an AppSetting deletes others (except itself)."""
        # The AppSetting model only allows one active setting
        # Due to the pk being 'active=True', creating two with same pk is an update
        setting1 = AppSetting(active=True)
        setting1.save()
        # Creating another and saving should work
        setting1.use_alternative_map = True
        setting1.save()
        assert AppSetting.objects.count() == 1
        assert AppSetting.objects.get(active=True).use_alternative_map is True


class TestHuntEvent:
    """Tests for HuntEvent model."""

    def test_hunt_event_creation(self, user: User) -> None:
        """HuntEvent should be created with correct values."""
        event = HuntEvent.objects.create(
            time=timezone.now(),
            kind=HuntEvent.EventKind.HINT_REQ,
            user=user,
            level=1,
        )
        assert event.kind == HuntEvent.EventKind.HINT_REQ
        assert event.level == 1

    def test_hunt_event_str_hint_req(self, user: User) -> None:
        """HuntEvent string representation for hint request."""
        event = HuntEvent.objects.create(
            time=timezone.now(),
            kind=HuntEvent.EventKind.HINT_REQ,
            user=user,
            level=1,
        )
        assert "requested a hint on" in str(event)

    def test_hunt_event_str_hint_rel(self, user: User) -> None:
        """HuntEvent string representation for hint released."""
        event = HuntEvent.objects.create(
            time=timezone.now(),
            kind=HuntEvent.EventKind.HINT_REL,
            user=user,
            level=1,
        )
        assert "saw a hint on" in str(event)

    def test_hunt_event_str_clue_adv(self, user: User) -> None:
        """HuntEvent string representation for level advance."""
        event = HuntEvent.objects.create(
            time=timezone.now(),
            kind=HuntEvent.EventKind.CLUE_ADV,
            user=user,
            level=2,
        )
        assert "progressed to" in str(event)


class TestChatMessage:
    """Tests for ChatMessage model."""

    def test_chat_message_creation(self, user: User, level: Level) -> None:
        """ChatMessage should be created with correct values."""
        message = ChatMessage.objects.create(
            team=user,
            level=level,
            name="Player1",
            content="Hello world",
        )
        assert message.team == user
        assert message.level == level
        assert message.name == "Player1"
        assert message.content == "Hello world"

    def test_chat_message_str(self, user: User, level: Level) -> None:
        """ChatMessage string representation."""
        message = ChatMessage.objects.create(
            team=user,
            level=level,
            name="Player1",
            content="Hello world",
        )
        msg_str = str(message)
        assert user.get_username() in msg_str
        assert "Player1" in msg_str
        assert "Hello world" in msg_str

    def test_chat_messages_ordered_by_date(self, user: User, level: Level) -> None:
        """ChatMessages should be ordered by date_added."""
        msg1 = ChatMessage.objects.create(
            team=user, level=level, name="A", content="First"
        )
        msg2 = ChatMessage.objects.create(
            team=user, level=level, name="B", content="Second"
        )
        messages = list(ChatMessage.objects.all())
        assert messages[0] == msg1
        assert messages[1] == msg2
