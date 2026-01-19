from django.contrib import admin
from django.contrib.admin.decorators import register
from .models import (
    Schema,
    SchemaRef,
    DocumentationItem,
    Organization,
    Profile
)


@register(Schema)
class SchemaAdmin(admin.ModelAdmin):
    list_display = ['name']


@register(SchemaRef)
class SchemaRefAdmin(admin.ModelAdmin):
    list_display = ['schema', 'url']


@register(DocumentationItem)
class DocumentationItemAdmin(admin.ModelAdmin):
    list_display = ['schema', 'name', 'url']


@register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']


@register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization']
