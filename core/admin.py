from django.contrib import admin
from django.contrib.admin.decorators import register
from .models import (Schema,
                     SchemaVersion,
                     SchemaRef,
                     SchemaDocumentationItem,
                     SchemaVersionDocumentationItem)


@register(Schema)
class SchemaAdmin(admin.ModelAdmin):
    list_display = ['name']


@register(SchemaVersion)
class SchemaVersionAdmin(admin.ModelAdmin):
    list_display = ['schema', 'name', 'published_at']


@register(SchemaRef)
class SchemaRefAdmin(admin.ModelAdmin):
    list_display = ['url', 'format', 'schema_version']


@register(SchemaDocumentationItem)
class SchemaDocumentationItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'url', 'format', 'schema']


@register(SchemaVersionDocumentationItem)
class SchemaVersionDocumentationItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'url', 'format', 'get_schema_versions']

    # Prefetch schema_versions so we can show them in the list display
    # without running n additional queries
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('schema_versions')

    def get_schema_versions(self, obj):
        return ", ".join([v.schema_versions for v in obj.schema_versions.all()])
     
class SchemaDocumentationItem(admin.ModelAdmin):
    list_display = ['name', 'url', 'format', 'schema']

