from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User

class BaseModel(models.Model):
    class Meta:
        abstract = True

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.RESTRICT)

    @classmethod
    def create(cls, created_by):
        return cls(created_by=created_by)


class Schema(BaseModel):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    def latest_reference(self):
        return self.schemaref_set.order_by('-created_at').first()
    
    def latest_readme(self):
        return self.documentationitem_set.filter(role=DocumentationItem.DocumentationItemRole.README).order_by('-created_at').first()
    

class ReferenceItem(BaseModel):
    class Meta:
        abstract = True

    url = models.URLField()

    def __str__(self):
        return self.url


class SchemaRef(ReferenceItem):
    schema = models.ForeignKey(Schema, on_delete=models.CASCADE)


class DocumentationItem(ReferenceItem):
    class DocumentationItemRole(models.TextChoices):
        README = 'readme'

    class DocumentationItemFormat(models.TextChoices):
        Markdown = 'markdown'

    name = models.CharField(max_length=300)
    description = models.TextField(blank=True, null=True)
    schema = models.ForeignKey(Schema, on_delete=models.CASCADE)
    role = models.CharField(max_length=100, choices=DocumentationItemRole, blank=True, null=True)
    format = models.CharField(max_length=100, choices=DocumentationItemFormat, blank=True, null=True)

    def __str__(self):
        return self.name

