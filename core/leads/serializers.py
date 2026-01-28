# repo-root/backend/core/leads/serializers.py

from rest_framework import serializers
from core.leads.models import Lead

from core.leads.models import LeadEvent, LeadNote

class LeadListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = [
            "id",
            "tenant_id",
            "chatbot_id",
            "conversation_id",
            "name",
            "primary_email",
            "phone",
            "status",
            "email_verified",
            "verified_at",
            "created_at",
            "updated_at",
        ]


class LeadDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = [
            "id",
            "tenant_id",
            "chatbot_id",
            "conversation_id",
            "name",
            "primary_email",
            "phone",
            "status",
            "email_verified",
            "verified_at",
            "meta_json",
            "created_at",
            "updated_at",
            "deleted_at",
        ]


class LeadUpdateSerializer(serializers.Serializer):
    # Only allow safe fields to be edited from dashboard
    name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=32)
    status = serializers.ChoiceField(required=False, choices=Lead.Status.choices)
    meta = serializers.DictField(required=False)

    def validate(self, attrs):
        if "name" in attrs:
            attrs["name"] = (attrs.get("name") or "").strip()
        if "phone" in attrs:
            attrs["phone"] = (attrs.get("phone") or "").strip()
        if "meta" in attrs and attrs["meta"] is None:
            attrs["meta"] = {}
        return attrs


class LeadEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadEvent
        fields = [
            "id",
            "type",
            "source",
            "actor_user_id",
            "data_json",
            "created_at",
        ]


class LeadNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadNote
        fields = [
            "id",
            "body",
            "created_by_user_id",
            "updated_by_user_id",
            "created_at",
            "updated_at",
        ]


class LeadNoteCreateSerializer(serializers.Serializer):
    body = serializers.CharField(min_length=1, max_length=5000)


class LeadNoteUpdateSerializer(serializers.Serializer):
    body = serializers.CharField(min_length=1, max_length=5000)

class LeadTouchSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)
