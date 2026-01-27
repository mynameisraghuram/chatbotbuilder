from datetime import datetime, timezone as tz

from django.conf import settings
from opensearchpy import OpenSearch


def get_client() -> OpenSearch:
    return OpenSearch(settings.OPENSEARCH_URL)


def leads_index_name() -> str:
    # matches your existing index naming: chatbuilder-leads
    return f"{settings.OPENSEARCH_INDEX_PREFIX}-leads"


def upsert_lead_doc(*, lead) -> None:
    client = get_client()
    index = leads_index_name()

    now = datetime.now(tz=tz.utc).isoformat()

    doc = {
        "tenant_id": str(lead.tenant_id),
        "lead_id": str(lead.id),
        "chatbot_id": str(lead.chatbot_id),
        "conversation_id": str(lead.conversation_id) if lead.conversation_id else "",
        "name": lead.name or "",
        "email": lead.primary_email or "",
        "phone": lead.phone or "",
        "status": lead.status,
        "email_verified": bool(lead.email_verified),
        "created_at": lead.created_at.isoformat() if lead.created_at else now,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else now,
    }

    # Use lead_id as _id so updates overwrite
    client.index(index=index, id=str(lead.id), body=doc, refresh=True)
