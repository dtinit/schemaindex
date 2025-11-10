from factory.django import DjangoModelFactory
from django.contrib.auth.models import User
import factory
from datetime import timezone
from core.models import (
    BaseModel, Schema, ReferenceItem, SchemaRef, DocumentationItem
)


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Faker('user_name')
    email = factory.Faker('email')
    password = factory.django.Password('testpassword')


class BaseModelFactory(DjangoModelFactory):
    created_by = factory.SubFactory(UserFactory)


class SchemaFactory(BaseModelFactory):
    class Meta:
         model = Schema
    
    name = factory.Faker('bs')
    published_at = factory.Faker("past_datetime", tzinfo=timezone.utc)


class ReferenceItemFactory(BaseModelFactory):
    class Meta:
        model = ReferenceItem

    url = factory.Faker('url')


class SchemaRefFactory(ReferenceItemFactory):
    class Meta:
        model = SchemaRef

    schema = factory.SubFactory(SchemaFactory)


class DocumentationItemFactory(ReferenceItemFactory):
    class Meta:
        model = DocumentationItem

    name = factory.Faker('bs')
    description = factory.Faker('paragraph')
    schema = factory.SubFactory(SchemaFactory)
    role = factory.Iterator(DocumentationItem.DocumentationItemRole.values)
    format = factory.Iterator(DocumentationItem.DocumentationItemFormat.values)

