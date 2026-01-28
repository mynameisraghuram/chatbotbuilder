from django.urls import path
from core.leads.api import leads_list, leads_detail, lead_timeline, lead_notes, lead_note_detail

urlpatterns = [
    path("leads", leads_list, name="leads-list"),
    path("leads/<uuid:lead_id>", leads_detail, name="leads-detail"),
    path("leads/<uuid:lead_id>/timeline", lead_timeline, name="leads-timeline"),

    # A7.8 notes
    path("leads/<uuid:lead_id>/notes", lead_notes, name="lead-notes"),
    path("leads/<uuid:lead_id>/notes/<uuid:note_id>", lead_note_detail, name="lead-note-detail"),
]
