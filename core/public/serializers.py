from rest_framework import serializers


class PublicChatRequestSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField(required=False)
    message = serializers.CharField()

    # optional identity fields
    external_user_id = serializers.CharField(required=False, allow_blank=True)
    session_id = serializers.CharField(required=False, allow_blank=True)
    user_email = serializers.EmailField(required=False, allow_blank=True)

    meta = serializers.JSONField(required=False)
