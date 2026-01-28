from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.leads.models_export import LeadExport
from core.leads. import export_leads_csv


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def export_leads(request):
    tenant_id = getattr(request, "tenant_id", None)

    exp = LeadExport.objects.create(
        tenant_id=tenant_id,
        requested_by_user_id=request.user.id,
    )

    export_leads_csv.delay(exp.id)

    return Response({"export_id": exp.id, "status": "queued"}, status=202)
