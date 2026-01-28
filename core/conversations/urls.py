from django.urls import path
from core.conversations.api import (
    conversations_list,
    conversations_search,
    conversation_detail,
    conversation_lead_get,
    conversation_lead_link,
)

urlpatterns = [
    path("conversations", conversations_list, name="conversations-list"),
    path("conversations/search", conversations_search, name="conversations-search"),
    path("conversations/<uuid:conversation_id>", conversation_detail, name="conversation-detail"),

    path("conversations/<uuid:conversation_id>/lead", conversation_lead_get, name="conversation-lead-get"),
    path("conversations/<uuid:conversation_id>/lead/link", conversation_lead_link, name="conversation-lead-link"),
]
