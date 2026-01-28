from rest_framework import serializers


class NotificationPreferenceOutSerializer(serializers.Serializer):
    tenant_id = serializers.UUIDField()
    user_id = serializers.UUIDField()

    email_enabled = serializers.BooleanField()
    webhook_enabled = serializers.BooleanField()

    digest_mode = serializers.ChoiceField(choices=["off", "daily", "weekly"])
    digest_hour = serializers.IntegerField(required=False, allow_null=True)


class NotificationPreferenceUpdateSerializer(serializers.Serializer):
    email_enabled = serializers.BooleanField(required=False)
    webhook_enabled = serializers.BooleanField(required=False)

    digest_mode = serializers.ChoiceField(choices=["off", "daily", "weekly"], required=False)
    digest_hour = serializers.IntegerField(required=False, allow_null=True)

    def validate_digest_hour(self, value):
        if value is None:
            return None
        if not (0 <= int(value) <= 23):
            raise serializers.ValidationError("digest_hour must be 0..23")
        return int(value)

    def validate(self, attrs):
        mode = attrs.get("digest_mode")
        hour = attrs.get("digest_hour", None)
        if mode in ("daily", "weekly") and hour is None:
            # sensible default: 9 AM if not provided
            attrs["digest_hour"] = 9
        if mode == "off":
            attrs["digest_hour"] = None
        return attrs
