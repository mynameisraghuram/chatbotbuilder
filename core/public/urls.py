from django.urls import path
from core.public.views import PublicPingView, PublicChatView

urlpatterns = [
    path("public/ping", PublicPingView.as_view(), name="public-ping"),
    path("public/chat", PublicChatView.as_view(), name="public-chat"),
]
