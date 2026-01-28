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


class KnowledgeSourceCreateSerializer(serializers.Serializer):
    # For /v1/knowledge-sources (url/text)
    source_type = serializers.ChoiceField(choices=[KnowledgeSource.SourceType.TEXT, KnowledgeSource.SourceType.URL])
    title = serializers.CharField(required=False, allow_blank=True)

    input_text = serializers.CharField(required=False, allow_blank=True)
    input_url = serializers.URLField(required=False, allow_blank=True)

    def validate(self, attrs):
        st = attrs.get("source_type")
        if st == KnowledgeSource.SourceType.TEXT and not attrs.get("input_text"):
            raise serializers.ValidationError({"input_text": "Required for source_type=text"})
        if st == KnowledgeSource.SourceType.URL and not attrs.get("input_url"):
            raise serializers.ValidationError({"input_url": "Required for source_type=url"})
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
            "stage",
            "progress_percent",
            "attempts",
            "error_code",
            "error_message",
            "last_error_at",
            "started_at",
            "finished_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id", "tenant", "status", "stage", "progress_percent",
            "attempts", "error_code", "error_message", "last_error_at",
            "started_at", "finished_at", "created_at", "updated_at"
        ]
