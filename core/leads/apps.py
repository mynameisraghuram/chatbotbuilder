from django.apps import AppConfig


class LeadsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core.leads"

    def ready(self):
        # register signals
        from . import signals  # noqa: F401
        from . import signals_events  # noqa: F401
