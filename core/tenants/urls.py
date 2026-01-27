from django.urls import path
from .api import tenant_me

urlpatterns = [
    path("tenants/me", tenant_me, name="tenant-me"),
]
