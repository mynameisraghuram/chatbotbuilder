from django.urls import path
from core.leads.api import leads_list, leads_detail, lead_timeline

urlpatterns = [
    path("leads", leads_list, name="leads-list"),
    path("leads/<uuid:lead_id>", leads_detail, name="leads-detail"),
    path("leads/<uuid:lead_id>/timeline", lead_timeline, name="leads-timeline"),
]
