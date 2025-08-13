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
    class Format(models.TextChoices):
        JSON = 'json_schema'

    name = models.CharField(max_length=200) # e.g. "Docker Compose file"
    

class SchemaVersion(BaseModel):
    name = models.CharField(max_length=200) # e.g. "3.0.1"
    schema = models.ForeignKey(Schema, on_delete=models.CASCADE)
    published_at = models.DateTimeField(blank=True, null=True)


class ReferenceItem(BaseModel):
    class Meta:
        abstract = True

    url = models.URLField()
    format = models.CharField(max_length=200, choices=Schema.Format)


class SchemaRef(ReferenceItem):
    schema_version = models.OneToOneField(SchemaVersion, on_delete=models.CASCADE)


class DocumentationItem(ReferenceItem):
    name = models.CharField(max_length=300)
    description = models.TextField(blank=True, null=True)
    schema = models.ForeignKey(Schema, on_delete=models.CASCADE, blank=True, null=True)
    schema_version = models.ForeignKey(SchemaVersion, on_delete=models.CASCADE, blank=True, null=True)
    
    class Meta:
        #XOR schema and schema_version
        constraints = [
            models.CheckConstraint(
                check=(Q(schema__isnull=True) & Q(schema_version__isnull=False)) |
                       (Q(schema__isnull=False) & Q(schema_version__isnull=True)),
                name='schema_xor_schema_version'
            )
        ]

