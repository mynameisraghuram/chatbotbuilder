from django.core.management.base import BaseCommand
from core.common.opensearch import get_client

class Command(BaseCommand):
    help = "Ping OpenSearch and print cluster info."

    def handle(self, *args, **options):
        client = get_client()
        info = client.info()
        self.stdout.write(self.style.SUCCESS(f"OpenSearch OK: {info.get('version', {}).get('number', 'unknown')}"))
