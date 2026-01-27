from rest_framework import serializers
from core.knowledge.models import KnowledgeSource, IngestionJob


class KnowledgeSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeSource
        fields = [
            "id",
            "tenant",
            "source_type",
            "title",
            "input_text",
            "input_url",
            "input_file",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]

    def validate(self, attrs):
        source_type = attrs.get("source_type") or getattr(self.instance, "source_type", None)
        if source_type == KnowledgeSource.SourceType.TEXT:
            if not (attrs.get("input_text") or getattr(self.instance, "input_text", "")):
                raise serializers.ValidationError("input_text is required for source_type=text")
        if source_type == KnowledgeSource.SourceType.URL:
            if not (attrs.get("input_url") or getattr(self.instance, "input_url", "")):
                raise serializers.ValidationError("input_url is required for source_type=url")
        if source_type == KnowledgeSource.SourceType.FILE:
            if not (attrs.get("input_file") or getattr(self.instance, "input_file", None)):
                raise serializers.ValidationError("input_file is required for source_type=file")
        return attrs


class IngestionJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = IngestionJob
        fields = [
            "id",
            "tenant",
            "source",
            "idempotency_key",
            "status",
            "attempts",
            "error_code",
            "error_message",
            "started_at",
            "finished_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "tenant", "status", "attempts", "error_code", "error_message", "started_at", "finished_at", "created_at", "updated_at"]
