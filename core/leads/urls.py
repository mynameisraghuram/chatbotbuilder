# repo-root/backend/core/leads/urls.py

from django.urls import path
from core.leads.api import leads_list, leads_detail

urlpatterns = [
    path("leads", leads_list, name="leads-list"),
    path("leads/<uuid:lead_id>", leads_detail, name="leads-detail"),
]
