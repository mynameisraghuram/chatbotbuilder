from rest_framework import serializers


class PublicChatRequestSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField(required=False)
    message = serializers.CharField()

    # optional identity fields
    external_user_id = serializers.CharField(required=False, allow_blank=True)
    session_id = serializers.CharField(required=False, allow_blank=True)
    user_email = serializers.EmailField(required=False, allow_blank=True)

    meta = serializers.JSONField(required=False)



class PublicLeadCaptureSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=32)
    meta = serializers.DictField(required=False)

    def validate(self, attrs):
        name = (attrs.get("name") or "").strip()
        email = (attrs.get("email") or "").strip()
        phone = (attrs.get("phone") or "").strip()

        if not (name or email or phone):
            raise serializers.ValidationError("At least one of name/email/phone is required")

        attrs["name"] = name
        attrs["email"] = email
        attrs["phone"] = phone
        attrs["meta"] = attrs.get("meta") or {}
        return attrs


class PublicOtpRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PublicOtpConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=4, max_length=8)