from django.urls import path
from .views import index, app, human_chat_view

urlpatterns = [
    path('', index, name='index'),
    path('app/', app, name='app'),
    path('human-chat/<str:room_name>/', human_chat_view, name='human_chat'),
]