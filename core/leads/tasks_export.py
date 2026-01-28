import csv, io
from celery import shared_task
from django.utils import timezone

from core.leads.models import Lead
from core.leads.models_export import LeadExport
# TODO: Update the import path below to match the actual location of upload_bytes in your project
from core.common.storage_utils import upload_bytes



@shared_task
def export_leads_csv(export_id):
    exp = LeadExport.objects.filter(id=export_id).first()
    if not exp:
        return

    exp.status = "processing"
    exp.save(update_fields=["status"])

    try:
        qs = Lead.objects.filter(tenant_id=exp.tenant_id, deleted_at__isnull=True)

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Name", "Email", "Phone", "Status", "Created"])

        for l in qs.iterator():
            writer.writerow([
                l.name,
                l.primary_email,
                l.phone,
                l.status,
                l.created_at.isoformat(),
            ])

        key = f"exports/leads_{exp.id}.csv"
        url = upload_bytes(buf.getvalue().encode(), key, content_type="text/csv")

        exp.status = "done"
        exp.file_url = url
        exp.save(update_fields=["status", "file_url"])

    except Exception as e:
        exp.status = "failed"
        exp.error = str(e)
        exp.save(update_fields=["status", "error"])
