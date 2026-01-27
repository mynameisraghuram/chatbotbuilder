from django.urls import path
from .api import entitlements

urlpatterns = [
    path("entitlements", entitlements, name="entitlements"),
]
