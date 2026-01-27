from django.urls import path
from core.analytics.api import chatbot_analytics, chatbot_trends

urlpatterns = [
    path("analytics/chatbots/<uuid:chatbot_id>", chatbot_analytics, name="analytics-chatbot"),
    path("analytics/chatbots/<uuid:chatbot_id>/trends", chatbot_trends, name="analytics-chatbot-trends"),
]
