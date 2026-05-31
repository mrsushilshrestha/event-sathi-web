from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/events/$', consumers.EventConsumer.as_asgi()),
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
    re_path(r'ws/chat/$', consumers.ChatConsumer.as_asgi()),
    re_path(r'ws/attendance/(?P<event_id>\d+)/$', consumers.AttendanceConsumer.as_asgi()),
]
