"""Tests for chat WebSocket consumers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator

from hunt.chat.consumers import ChatConsumer, async_get_level, async_is_level_allowed
from hunt.models import ChatMessage, Level

if TYPE_CHECKING:
    from collections.abc import Callable

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


def make_communicator(user: User, level: int) -> WebsocketCommunicator:
    """Create a WebsocketCommunicator for the ChatConsumer with a given user/level."""
    communicator = WebsocketCommunicator(
        ChatConsumer.as_asgi(),
        f"/level/{level}/",
    )
    communicator.scope["user"] = user
    communicator.scope["url_route"] = {"kwargs": {"level": level}}
    return communicator


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestChatConsumerConnect:
    """Tests for ChatConsumer.connect."""

    async def test_connect_accepted_for_allowed_user(
        self, user: User, level: Level
    ) -> None:
        """User on current level should connect successfully."""
        communicator = make_communicator(user, level.number)
        connected, _ = await communicator.connect()

        assert connected is True
        await communicator.disconnect()

    async def test_connect_rejected_for_disallowed_level(
        self, user: User, level: Level
    ) -> None:
        """User should be rejected when accessing a level above their progress."""
        communicator = make_communicator(user, level.number + 1)
        connected, _ = await communicator.connect()

        assert connected is False

    async def test_connect_rejected_for_zero_level(self, user: User) -> None:
        """Level 0 should always be rejected."""
        communicator = make_communicator(user, 0)
        connected, _ = await communicator.connect()

        assert connected is False

    async def test_connect_accepted_for_staff_any_level(
        self, staff_user: User, level: Level
    ) -> None:
        """Staff user should be able to connect to any level."""
        communicator = make_communicator(staff_user, level.number)
        connected, _ = await communicator.connect()

        assert connected is True
        await communicator.disconnect()

    async def test_connect_accepted_for_past_level(
        self, user: User, create_level: Callable[..., Level]
    ) -> None:
        """User should connect to a level below their current progress."""
        await database_sync_to_async(create_level)(number=1)
        await database_sync_to_async(create_level)(number=2)
        user.huntinfo.level = 2
        await sync_to_async(user.huntinfo.save)()

        communicator = make_communicator(user, 1)
        connected, _ = await communicator.connect()

        assert connected is True
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestChatConsumerDisconnect:
    """Tests for ChatConsumer.disconnect."""

    async def test_disconnect_after_connect(self, user: User, level: Level) -> None:
        """Disconnect after a successful connect should not raise."""
        communicator = make_communicator(user, level.number)
        await communicator.connect()
        await communicator.disconnect()

    async def test_disconnect_without_connect(self, db: None) -> None:
        """Disconnect without a prior connect (room_group is None) should not raise."""
        _ = db
        consumer = ChatConsumer()
        # Simulate disconnect with no room_group set
        await consumer.disconnect(code=1000)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestChatConsumerReceiveJson:
    """Tests for ChatConsumer.receive_json and chat_message."""

    async def test_send_and_receive_message(self, user: User, level: Level) -> None:
        """Sending a message should echo it back via the group layer."""
        communicator = make_communicator(user, level.number)
        await communicator.connect()

        await communicator.send_json_to(
            {"message": "Hello team!", "username": "player1"}
        )

        response = await communicator.receive_json_from()
        assert response == {"message": "Hello team!", "username": "player1"}

        await communicator.disconnect()

    async def test_message_saved_to_database(self, user: User, level: Level) -> None:
        """Sending a message should persist it as a ChatMessage."""
        communicator = make_communicator(user, level.number)
        await communicator.connect()

        await communicator.send_json_to(
            {"message": "Persisted msg", "username": "player1"}
        )
        # Consume the echoed message
        await communicator.receive_json_from()

        count = await database_sync_to_async(ChatMessage.objects.count)()
        assert count == 1

        msg = await database_sync_to_async(ChatMessage.objects.first)()
        assert msg is not None
        assert msg.content == "Persisted msg"
        assert msg.name == "player1"

        await communicator.disconnect()

    async def test_multiple_messages_all_saved(self, user: User, level: Level) -> None:
        """Multiple messages should all be persisted."""
        communicator = make_communicator(user, level.number)
        await communicator.connect()

        for i in range(3):
            await communicator.send_json_to(
                {"message": f"msg {i}", "username": "player1"}
            )
            await communicator.receive_json_from()

        count = await database_sync_to_async(ChatMessage.objects.count)()
        assert count == 3

        await communicator.disconnect()

    async def test_message_linked_to_correct_team_and_level(
        self, user: User, level: Level
    ) -> None:
        """Saved ChatMessage should reference the connected user and level."""
        communicator = make_communicator(user, level.number)
        await communicator.connect()

        await communicator.send_json_to(
            {"message": "check refs", "username": "someone"}
        )
        await communicator.receive_json_from()

        @database_sync_to_async  # type: ignore[untyped-decorator]
        def get_message() -> ChatMessage | None:
            return ChatMessage.objects.select_related("team", "level").first()

        msg = await get_message()
        assert msg.team == user
        assert msg.level == level

        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestChatConsumerSaveMessage:
    """Tests for ChatConsumer.save_message directly."""

    async def test_save_message_creates_record(self, user: User, level: Level) -> None:
        """save_message should create a ChatMessage in the database."""
        consumer = ChatConsumer()
        consumer.team = user
        consumer.level = level

        await consumer.save_message("tester", "direct save test")

        count = await database_sync_to_async(ChatMessage.objects.count)()
        assert count == 1

        msg = await database_sync_to_async(ChatMessage.objects.first)()
        assert msg is not None
        assert msg.name == "tester"
        assert msg.content == "direct save test"


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestChatConsumerChatMessage:
    """Tests for ChatConsumer.chat_message (group broadcast handler)."""

    async def test_chat_message_sends_to_websocket(
        self, user: User, level: Level
    ) -> None:
        """The chat_message handler should forward the event to the WebSocket."""
        communicator = make_communicator(user, level.number)
        await communicator.connect()

        # Directly call chat_message on the consumer via the group layer
        consumer = ChatConsumer()
        consumer.team = user
        consumer.level = level
        consumer.room_group = f"{user.get_username()}_{level.number}"

        # Use the communicator to verify a round-trip instead
        await communicator.send_json_to(
            {"message": "broadcast test", "username": "broadcaster"}
        )
        response = await communicator.receive_json_from()
        assert response["message"] == "broadcast test"
        assert response["username"] == "broadcaster"

        await communicator.disconnect()
