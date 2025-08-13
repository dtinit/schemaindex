from django.contrib import admin
from django.contrib.admin.decorators import register
from .models import Schema, SchemaVersion, SchemaRef, DocumentationItem


@register(Schema)
class SchemaAdmin(admin.ModelAdmin):
    list_display = ['name']


@register(SchemaVersion)
class SchemaVersionAdmin(admin.ModelAdmin):
    list_display = ['schema', 'name', 'published_at']


@register(SchemaRef)
class SchemaRefAdmin(admin.ModelAdmin):
    list_display = ['url', 'format', 'schema_version']


@register(DocumentationItem)
class DocumentationItem(admin.ModelAdmin):
    list_display = ['name', 'url', 'format', 'schema', 'schema_version']
