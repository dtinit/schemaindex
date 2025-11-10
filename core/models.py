from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from datetime import datetime
from urllib.parse import urlparse

class BaseModel(models.Model):
    class Meta:
        abstract = True

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.RESTRICT)

    @classmethod
    def create(cls, created_by):
        return cls(created_by=created_by)


class PublicSchemaManager(models.Manager):
    def get_queryset(self):
        return (
            super().get_queryset().filter(
                published_at__isnull=False,
                published_at__lte=datetime.now()
            )
        )


class Schema(BaseModel):
    objects = models.Manager()
    public_objects = PublicSchemaManager()
    name = models.CharField(max_length=200)
    published_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.name

    @property
    def is_published(self):
        return self.published_at and self.published_at >= datetime.now()

    def _latest_documentation_item_of_type(self, role):
        return self.documentationitem_set.filter(role=role).order_by('-created_at').first()

    def latest_reference(self):
        return self.schemaref_set.order_by('-created_at').first()

    def latest_readme(self):
        return self._latest_documentation_item_of_type(role=DocumentationItem.DocumentationItemRole.README)

    def latest_license(self):
        return self._latest_documentation_item_of_type(role=DocumentationItem.DocumentationItemRole.License)
    
    def latest_rfc(self):
        return self._latest_documentation_item_of_type(role=DocumentationItem.DocumentationItemRole.RFC)

    def latest_w3c(self):
        return self._latest_documentation_item_of_type(role=DocumentationItem.DocumentationItemRole.W3C)


class ReferenceItem(BaseModel):
    class Meta:
        abstract = True

    url = models.URLField()

    @classmethod
    def get_published_by_domain_and_path(other_url):
        published_schema_refs = self.select_related('schema').exclude(
            schema__published_at__is_null=True
        )
        matching_published_schema_refs = [
            schema_ref for schema_ref in published_schema_refs
            if schema_ref.has_same_domain_and_path(url)
        ]
        return matching_published_schema_refs

    def __str__(self):
        return self.url

    def has_same_domain_and_path(other_url):
        parsed_url_1 = urlparse(self.url)
        parsed_url_2 = urlparse(other_url)
        return parsed_url_1.netloc == parsed_url_2.netloc and parsed_url_1.path == parsed_url_2.path


class SchemaRef(ReferenceItem):
    schema = models.ForeignKey(Schema, on_delete=models.CASCADE)


class DocumentationItem(ReferenceItem):
    class DocumentationItemRole(models.TextChoices):
        README = 'readme'
        License = 'license'
        RFC = 'rfc'
        W3C = 'w3c'

    class DocumentationItemFormat(models.TextChoices):
        Markdown = 'markdown'
        PlainText = 'plaintext'

    name = models.CharField(max_length=300)
    description = models.TextField(blank=True, null=True)
    schema = models.ForeignKey(Schema, on_delete=models.CASCADE)
    role = models.CharField(max_length=100, choices=DocumentationItemRole, blank=True, null=True)
    format = models.CharField(max_length=100, choices=DocumentationItemFormat, blank=True, null=True)

    def __str__(self):
        return self.name

