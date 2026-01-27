import pytest
from django.core.management import call_command
from core.common.opensearch import get_client

@pytest.mark.django_db
def test_opensearch_ping_command_smoke():
    client = get_client()
    try:
        client.info()
    except Exception:
        pytest.skip("OpenSearch not reachable in this test environment")
    call_command("opensearch_ping")
