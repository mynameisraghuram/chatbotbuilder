from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from opensearchpy import OpenSearch
from django.conf import settings


class SearchView(APIView):
    def get(self, request):
        tenant_id = request.headers.get("X-Tenant-Id") or request.headers.get("x-tenant-id")
        if not tenant_id:
            return Response({"detail": "X-Tenant-Id required"}, status=status.HTTP_400_BAD_REQUEST)

        q = request.query_params.get("q", "").strip()
        if not q:
            return Response({"results": [], "total": 0}, status=status.HTTP_200_OK)

        page = int(request.query_params.get("page", "1"))
        page_size = min(int(request.query_params.get("page_size", "10")), 50)
        start = (page - 1) * page_size

        client = OpenSearch(settings.OPENSEARCH_URL)
        index_name = f"{settings.OPENSEARCH_INDEX_PREFIX}-documents"

        body = {
            "from": start,
            "size": page_size,
            "query": {
                "bool": {
                    "must": [{"match": {"content": q}}],
                    "filter": [{"term": {"tenant_id": str(tenant_id)}}],
                }
            },
        }

        resp = client.search(index=index_name, body=body)
        hits = resp.get("hits", {})
        total = hits.get("total", {}).get("value", 0)
        results = [
            {
                "id": h.get("_id"),
                "score": h.get("_score"),
                **(h.get("_source") or {}),
            }
            for h in hits.get("hits", [])
        ]

        return Response({"results": results, "total": total, "page": page, "page_size": page_size})
