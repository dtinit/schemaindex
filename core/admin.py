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
    APIKey
)
from .middleware.rate_limit import get_profile_rate_limit_key

def format_date_only(obj, date_field):
    return date_field.strftime("%b. %d, %Y") if date_field else "-"

@register(Schema)
class SchemaAdmin(admin.ModelAdmin):
    list_display = ['name', 'formatted_is_published', 'get_org', 'formatted_created_at']
    list_filter = ('created_at', 'published_at')
    readonly_fields = ('is_published', 'get_org')

    @admin.display(description="Created At", ordering='created_at')
    def formatted_created_at(self, obj):
        return format_date_only(obj, obj.created_at)

    @admin.display(description="Org", ordering='created_by__profile__organization')
    def get_org(self, obj):
        return obj.created_by.profile.organization

    @admin.display(description="Published", ordering='published_at')
    def formatted_is_published(self, obj):
        return '✓' if obj.is_published else ''


@register(SchemaRef)
class SchemaRefAdmin(admin.ModelAdmin):
    list_display = ['name', 'schema', 'url']
    search_fields = ['schema__name', 'schema__created_by__profile__organization__name']


@register(DocumentationItem)
class DocumentationItemAdmin(admin.ModelAdmin):
    list_display = ['schema', 'name', 'url']
    search_fields = ['name', 'schema__name', 'schema__created_by__profile__organization__name']
    list_filter = ['role']


@register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']


@admin.action(description='Reset API Rate Limits')
def reset_rate_limit(modeladmin, request, queryset):
    for profile in queryset:
        # Match the key format used in your middleware
        cache_key = get_profile_rate_limit_key(profile)
        cache.delete(cache_key)
    
    messages.success(request, f'Rate limits reset for {queryset.count()} profiles.')


@register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization']
    actions = [reset_rate_limit]


@register(PermanentURL)
class PermanentURLAdmin(admin.ModelAdmin):
    list_display = ['content_object', 'url']


@register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ['prefix', 'profile']
