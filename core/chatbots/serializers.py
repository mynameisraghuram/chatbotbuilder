from rest_framework import serializers
from core.chatbots.models import Chatbot


class ChatbotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chatbot
        fields = [
            "id",
            "tenant",
            "name",
            "status",
            "tone",
            "branding_json",
            "lead_capture_enabled",
            "citations_enabled",
            "created_at",
            "updated_at",
            "deleted_at",
        ]
        read_only_fields = ["id", "tenant", "created_at", "updated_at", "deleted_at"]


class ChatbotCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    tone = serializers.ChoiceField(choices=Chatbot.Tone.choices, required=False)
    branding_json = serializers.JSONField(required=False)
    lead_capture_enabled = serializers.BooleanField(required=False)
    citations_enabled = serializers.BooleanField(required=False)


class ChatbotUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    status = serializers.CharField(required=False)
    citations_enabled = serializers.BooleanField(required=False)

    # ✅ new
    lead_capture_enabled = serializers.BooleanField(required=False)
