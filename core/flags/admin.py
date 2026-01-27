from django.contrib import admin
from .models import FeatureFlag, TenantFeatureFlag

@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ("key", "enabled_by_default", "description", "created_at")
    search_fields = ("key", "description")

@admin.register(TenantFeatureFlag)
class TenantFeatureFlagAdmin(admin.ModelAdmin):
    list_display = ("tenant", "key", "is_enabled", "updated_at")
    list_filter = ("is_enabled",)
    search_fields = ("tenant__name", "key__key")
