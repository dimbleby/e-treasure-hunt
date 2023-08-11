import json
from typing import TYPE_CHECKING

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from hunt.models import ChatMessage, Level

if TYPE_CHECKING:
    from django.contrib.auth.models import User


class ChatConsumer(AsyncWebsocketConsumer):  # type: ignore[misc]
    def __init__(self) -> None:
        super().__init__()
        self.team: User | None = None
        self.level: Level | None = None
        self.room_group: str | None = None

    async def connect(self) -> None:
        user: User = self.scope["user"]
        level: int = self.scope["url_route"]["kwargs"]["level"]

        if not user.is_authenticated:
            await self.close()
            return

        self.team = user
        self.level = await self.get_level(level)
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
    async def receive(self, text_data: str) -> None:
        data = json.loads(text_data)
        message = data["message"]
        username = data["username"]

        await self.save_message(username, message)

        # Send message to room group
        assert self.room_group is not None
        await self.channel_layer.group_send(
            self.room_group,
            {"type": "chat_message", "message": message, "username": username},
        )

    # Receive message from room group
    async def chat_message(self, event: dict[str, str]) -> None:
        message = event["message"]
        username = event["username"]

        # Send message to WebSocket
        await self.send(
            text_data=json.dumps({"message": message, "username": username})
        )

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
    def get_level(self, number: int) -> Level:
        return Level.objects.get(number=number)
