from django.urls import path
from core.search.views import SearchView
from core.search.leads_api import search_leads

urlpatterns = [
    path("search/", SearchView.as_view(), name="search"),
    path("search/leads", search_leads, name="search-leads"),
]
