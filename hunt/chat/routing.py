from django.urls import path

from hunt.chat import consumers

websocket_urlpatterns = [
    path("level/<int:level>/", consumers.ChatConsumer.as_asgi()),
]
