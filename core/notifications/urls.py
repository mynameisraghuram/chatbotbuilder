from django.urls import path
from core.notifications.api import my_notification_preferences

urlpatterns = [
    path("notifications/preferences/me", my_notification_preferences, name="my-notification-preferences"),
]
