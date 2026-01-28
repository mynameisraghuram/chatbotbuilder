from rest_framework import serializers


class WebhookEndpointOutSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    tenant_id = serializers.UUIDField()
    url = serializers.URLField()
    is_active = serializers.BooleanField()
    events = serializers.ListField(child=serializers.CharField(), required=False)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class WebhookEndpointCreateSerializer(serializers.Serializer):
    url = serializers.URLField()
    is_active = serializers.BooleanField(required=False, default=True)
    events = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
        allow_empty=True,
    )

    def validate_events(self, value):
        if value is None:
            return []
        if len(value) > 50:
            raise serializers.ValidationError("Too many events (max 50).")
        cleaned = []
        for e in value:
            s = str(e).strip()
            if not s:
                continue
            if len(s) > 100:
                raise serializers.ValidationError("Event name too long.")
            cleaned.append(s)
        return cleaned


class WebhookEndpointUpdateSerializer(serializers.Serializer):
    url = serializers.URLField(required=False)
    is_active = serializers.BooleanField(required=False)
    events = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )

    def validate_events(self, value):
        if value is None:
            return []
        if len(value) > 50:
            raise serializers.ValidationError("Too many events (max 50).")
        cleaned = []
        for e in value:
            s = str(e).strip()
            if not s:
                continue
            if len(s) > 100:
                raise serializers.ValidationError("Event name too long.")
            cleaned.append(s)
        return cleaned
