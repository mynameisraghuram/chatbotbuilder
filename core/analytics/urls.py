from django.urls import path
from core.analytics.api import (
    chatbot_analytics,
    chatbot_trends,
    chatbot_top_queries,
    chatbot_gaps,
)

urlpatterns = [
    path("analytics/chatbots/<uuid:chatbot_id>", chatbot_analytics, name="analytics-chatbot"),
    path("analytics/chatbots/<uuid:chatbot_id>/trends", chatbot_trends, name="analytics-chatbot-trends"),
    path("analytics/chatbots/<uuid:chatbot_id>/top-queries", chatbot_top_queries, name="analytics-chatbot-top-queries"),
    path("analytics/chatbots/<uuid:chatbot_id>/gaps", chatbot_gaps, name="analytics-chatbot-gaps"),
]
