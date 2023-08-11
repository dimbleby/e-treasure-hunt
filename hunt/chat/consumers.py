import json

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import User

from hunt.models import ChatMessage


class ChatConsumer(AsyncWebsocketConsumer):  # type: ignore[misc]
    async def connect(self) -> None:
        room_name: str = self.scope["url_route"]["kwargs"]["room_name"]
        room_team, _room_level = room_name.rsplit("_", 1)
        self.room_name = room_name
        self.room_group_name = f"chat_{room_name}"
        self.team = room_team

        # Verify that the user is authenticated and is allowed into this room.
        user: User = self.scope["user"]
        if not user.is_authenticated:
            await self.close()
            return

        team = user.get_username()
        if team != self.team:
            await self.close()
            return

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(
        self,
        code: int,  # noqa: ARG002
    ) -> None:
        # Leave room group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    # Receive message from WebSocket
    async def receive(self, text_data: str) -> None:
        data = json.loads(text_data)
        message = data["message"]
        username = data["username"]

        await self.save_message(username, message)

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
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
        try:
            team_user = User.objects.get(username=self.team)
            ChatMessage.objects.create(
                name=username,
                team=team_user,
                room=self.room_name,
                content=message,
            )
        except User.DoesNotExist:
            # We don't know which team made this message, so don't save it
            pass
