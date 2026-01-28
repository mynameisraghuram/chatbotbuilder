from rest_framework import serializers


class LeadLiteSerializer(serializers.Serializer):
    """
    Defensive serializer: only returns fields if they exist on the Lead model.
    (Prevents breaks if your Lead schema evolves.)
    """
    id = serializers.CharField()
    name = serializers.CharField(required=False, allow_blank=True)
    email = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)

    def to_representation(self, instance):
        data = {"id": str(getattr(instance, "id"))}

        for f in ("name", "email", "phone"):
            if hasattr(instance, f):
                data[f] = getattr(instance, f) or ""

        for f in ("created_at", "updated_at"):
            if hasattr(instance, f):
                v = getattr(instance, f)
                data[f] = v.isoformat() if v else None

        return data
