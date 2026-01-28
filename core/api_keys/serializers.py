from rest_framework import serializers
from core.api_keys.models import ApiKey


class ApiKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiKey
        fields = ["id", "chatbot_id", "key_prefix", "status", "rate_limit_per_min", "created_at", "revoked_at"]
