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
    

class ReferenceItem(BaseModel):
    class Meta:
        abstract = True

    url = models.URLField()

    def __str__(self):
        return self.url


class SchemaRef(ReferenceItem):
    schema = models.ForeignKey(Schema, on_delete=models.CASCADE)


class DocumentationItem(ReferenceItem):
    name = models.CharField(max_length=300)
    description = models.TextField(blank=True, null=True)
    schema = models.ForeignKey(Schema, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

