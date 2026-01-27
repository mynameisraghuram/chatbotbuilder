from django.urls import path
from core.conversations.api import conversations_list, conversation_detail, conversations_search

urlpatterns = [
    path("conversations", conversations_list, name="conversations-list"),
    path("conversations/search", conversations_search, name="conversations-search"),
    path("conversations/<uuid:conversation_id>", conversation_detail, name="conversation-detail"),
]
