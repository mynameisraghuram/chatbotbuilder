from django.core.management.base import BaseCommand
from opensearchpy import OpenSearch
from django.conf import settings

class Command(BaseCommand):
    help = "Initialize OpenSearch indices"

    def handle(self, *args, **options):
        client = OpenSearch(settings.OPENSEARCH_URL)

        index_name = f"{settings.OPENSEARCH_INDEX_PREFIX}-documents"

        if client.indices.exists(index=index_name):
            self.stdout.write(self.style.WARNING(f"Index already exists: {index_name}"))
            return

        body = {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
            },
            "mappings": {
                "properties": {
                    "tenant_id": {"type": "keyword"},
                    "source_id": {"type": "keyword"},
                    "content": {"type": "text"},
                    "created_at": {"type": "date"},
                }
            },
        }

        client.indices.create(index=index_name, body=body)
        self.stdout.write(self.style.SUCCESS(f"Created index: {index_name}"))
