from django.contrib import admin
from core.conversations.models import Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "chatbot", "external_user_id", "session_id", "created_at", "updated_at")
    search_fields = ("external_user_id", "session_id", "user_email")
    list_filter = ("chatbot", "created_at")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "conversation", "role", "created_at")
    search_fields = ("content",)
    list_filter = ("role", "created_at")
