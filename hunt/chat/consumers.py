from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from hunt.models import ChatMessage, Level

if TYPE_CHECKING:
    from channels.layers import BaseChannelLayer
    from django.contrib.auth.models import User

    class UserMessage(TypedDict):
        username: str
        message: str


class ChatConsumer(AsyncJsonWebsocketConsumer):  # type: ignore[misc]
    def __init__(self) -> None:
        super().__init__()
        self.team: User | None = None
        self.level: Level | None = None
        self.room_group: str | None = None
        self.channel_layer: BaseChannelLayer

    async def connect(self) -> None:
        user: User = self.scope["user"]
        level: int = self.scope["url_route"]["kwargs"]["level"]

        if not user.is_authenticated:
            await self.close()
            return

        allowed = await async_is_level_allowed(user, level)
        if not allowed:
            await self.close()
            return

        self.team = user
        self.level = await async_get_level(level)
        self.room_group = f"{user.get_username()}_{level}"

        # Join room group
        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

    async def disconnect(
        self,
        code: int,  # noqa: ARG002
    ) -> None:
        if self.room_group is not None:
            await self.channel_layer.group_discard(self.room_group, self.channel_name)

    # Receive message from WebSocket
    async def receive_json(
        self,
        content: UserMessage,
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        message = content["message"]
        username = content["username"]

        await self.save_message(username, message)

        # Send message to room group
        assert self.room_group is not None
        await self.channel_layer.group_send(
            self.room_group,
            {"type": "chat.message", "message": message, "username": username},
        )

    # Receive message from room group
    async def chat_message(self, event: UserMessage) -> None:
        message = event["message"]
        username = event["username"]

        # Send message to WebSocket
        await self.send_json(content={"message": message, "username": username})

    @sync_to_async
    def save_message(self, username: str, message: str) -> None:
        chat_message = ChatMessage(
            team=self.team,
            level=self.level,
            name=username,
            content=message,
        )
        chat_message.full_clean()
        chat_message.save()


@sync_to_async
def async_get_level(number: int) -> Level:
    return Level.objects.get(number=number)


@sync_to_async
def async_is_level_allowed(user: User, level: int) -> int:
    if level <= 0:
        return False

    if user.is_staff:
        return True

    return level <= user.huntinfo.level
