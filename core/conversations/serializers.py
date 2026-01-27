from rest_framework import serializers
from core.conversations.models import Conversation, Message


class ConversationListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = [
            "id",
            "tenant_id",
            "chatbot_id",
            "external_user_id",
            "session_id",
            "user_email",
            "created_at",
            "updated_at",
        ]


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = [
            "id",
            "conversation_id",
            "role",
            "content",
            "meta_json",
            "created_at",
        ]


class ConversationDetailSerializer(serializers.ModelSerializer):
    messages = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id",
            "tenant_id",
            "chatbot_id",
            "external_user_id",
            "session_id",
            "user_email",
            "meta_json",
            "created_at",
            "updated_at",
            "messages",
        ]

    def get_messages(self, obj: Conversation):
        qs = Message.objects.filter(conversation=obj).order_by("created_at")
        return MessageSerializer(qs, many=True).data
