from django.contrib import admin
from django.contrib.admin.decorators import register
from .models import Schema, SchemaRef, DocumentationItem


@register(Schema)
class SchemaAdmin(admin.ModelAdmin):
    list_display = ['name']


@register(SchemaRef)
class SchemaRefAdmin(admin.ModelAdmin):
    list_display = ['schema', 'url']


@register(DocumentationItem)
class DocumentationItemAdmin(admin.ModelAdmin):
    list_display = ['schema', 'name', 'url']

