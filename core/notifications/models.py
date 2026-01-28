import uuid
from django.db import models
from django.utils import timezone


class NotificationPreference(models.Model):
    class DigestMode(models.TextChoices):
        OFF = "off", "Off"
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"

    id = models.BigAutoField(primary_key=True)

    tenant_id = models.UUIDField(db_index=True)
    user_id = models.UUIDField(db_index=True)

    email_enabled = models.BooleanField(default=True)
    webhook_enabled = models.BooleanField(default=True)

    digest_mode = models.CharField(
        max_length=10,
        choices=DigestMode.choices,
        default=DigestMode.OFF,
        db_index=True,
    )
    digest_hour = models.PositiveSmallIntegerField(null=True, blank=True)  # 0..23

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "notification_preferences"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "user_id"],
                name="uniq_notification_pref_tenant_user",
            )
        ]
        indexes = [
            models.Index(fields=["tenant_id", "user_id"]),
            models.Index(fields=["tenant_id", "digest_mode"]),
        ]

    def touch(self):
        self.updated_at = timezone.now()
        self.save(update_fields=["updated_at"])
