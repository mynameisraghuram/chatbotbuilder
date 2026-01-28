from django.urls import path
from core.audit.api import (
    audit_logs, 
)

urlpatterns = [
    # Define your audit-related URL patterns here
    path("audit/logs", audit_logs),

]