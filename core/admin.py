from django.contrib import admin, messages
from django.contrib.admin.decorators import register
from django.core.cache import cache
from .models import (
    Schema,
    SchemaRef,
    DocumentationItem,
    Organization,
    Profile,
    PermanentURL,
    APIKey,
)
from .middleware.rate_limit import get_user_rate_limit_key


def format_date_only(obj, date_field):
    return date_field.strftime("%b. %d, %Y") if date_field else "-"


@register(Schema)
class SchemaAdmin(admin.ModelAdmin):
    list_display = ["name", "formatted_is_published", "get_org", "formatted_created_at"]
    list_filter = ("created_at", "published_at")
    readonly_fields = ("is_published", "get_org")

    @admin.display(description="Created At", ordering="created_at")
    def formatted_created_at(self, obj):
        return format_date_only(obj, obj.created_at)

    @admin.display(description="Org", ordering="created_by__profile__organization")
    def get_org(self, obj):
        return obj.created_by.profile.organization

    @admin.display(description="Published", ordering="published_at")
    def formatted_is_published(self, obj):
        return "✓" if obj.is_published else ""

    def save_model(self, request, obj, form, change):
        # Passing this flag allows us to
        # override custom validation
        obj.save(is_admin_change=True)

    def delete_model(self, request, obj):
        # Passing this flag allows us to
        # override custom validation
        obj.delete(is_admin_change=True)


# See #373 and #385.
@admin.action(
    description="Refresh $id values for selected JSON schema refs (can take a while!)"
)
def refresh_id_values(modeladmin, request, queryset):
    """
    For a queryset of SchemaRefs selected in the UI,
    pull them from the database,
    filter out any that are not JSON or not fetchable,
    attempt to get the content, and finally (if successful)
    reparse the id_value ($id)
    """
    schema_refs = [
        schema_ref
        for schema_ref in queryset
        if schema_ref.language == "json" and schema_ref.is_content_fetchable
    ]
    changed_count = 0
    failed_ids = []

    for schema_ref in schema_refs:
        old_id_value = schema_ref.id_value
        try:
            # Fetch up front so a failed fetch doesn't
            # get saved as a missing $id
            schema_ref.get_content(refresh=True, update_and_notify_on_failure=False)
            # Content is cached; save will use it
            # to parse id_value.
            schema_ref.save(update_fields=["id_value"])
            if schema_ref.id_value != old_id_value:
                changed_count += 1

        except Exception:
            failed_ids.append(schema_ref.id)

    queryset_total = queryset.count()
    skipped_count = queryset_total - len(schema_refs)
    failed_count = len(failed_ids)
    messages.success(
        request,
        f"Finished processing {queryset_total} SchemaRefs: "
        f"{skipped_count} skipped (not JSON or not fetchable), "
        f"{changed_count} id_values updated, "
        f"{failed_count} failed.",
    )
    if failed_ids:
        messages.warning(
            request,
            f"Failed to refresh id_value for {failed_count} schema refs "
            f"(IDs: {', '.join(str(id) for id in failed_ids)}).",
        )


@register(SchemaRef)
class SchemaRefAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "schema", "url"]
    search_fields = ["schema__name", "schema__created_by__profile__organization__name"]
    actions = [refresh_id_values]


@register(DocumentationItem)
class DocumentationItemAdmin(admin.ModelAdmin):
    list_display = ["schema", "name", "url"]
    search_fields = [
        "name",
        "schema__name",
        "schema__created_by__profile__organization__name",
    ]
    list_filter = ["role"]


@register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]


@admin.action(description="Reset API Rate Limits")
def reset_rate_limit(modeladmin, request, queryset):
    for profile in queryset:
        cache_key = get_user_rate_limit_key(profile.user_id)
        cache.delete(cache_key)

    messages.success(request, f"Rate limits reset for {queryset.count()} profiles.")


@register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "organization"]
    actions = [reset_rate_limit]


@register(PermanentURL)
class PermanentURLAdmin(admin.ModelAdmin):
    list_display = ["content_object", "url"]


@register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ["prefix", "profile"]
