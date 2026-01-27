from django.urls import path
from core.analytics.api import chatbot_analytics

urlpatterns = [
    path("analytics/chatbots/<uuid:chatbot_id>", chatbot_analytics, name="analytics-chatbot"),
]
