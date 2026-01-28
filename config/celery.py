import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("chatbuilder")
app.config_from_object("django.conf:settings", namespace="CELERY")

# ✅ Ensure Celery imports tasks from these modules explicitly (deterministic)
app.conf.imports = (
    "core.common.tasks",
    "core.search.tasks",
    "core.knowledge.tasks",
    "core.leads.tasks_sla",
    "core.leads.tasks_delivery",
    "core.webhooks.tasks",
)

# ✅ Also allow normal autodiscovery for future apps
app.autodiscover_tasks()
