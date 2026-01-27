from django.urls import path, include
from rest_framework.routers import DefaultRouter

from core.chatbots.views import ChatbotViewSet
from core.chatbots.api import chatbot_update

router = DefaultRouter()
router.register(r"chatbots", ChatbotViewSet, basename="chatbots")

urlpatterns = [
    path("", include(router.urls)),
    path("chatbots/<uuid:chatbot_id>", chatbot_update, name="chatbot-update"),
]
