from django.urls import path
from .consumers import ChatConsumerDemo, HumanChatConsumer

websocket_urlpatterns = [
  path("ws/ai-demo/", ChatConsumerDemo.as_asgi()),
  path("ws/human-chat/<str:room_name>/", HumanChatConsumer.as_asgi()),  # NEW
]