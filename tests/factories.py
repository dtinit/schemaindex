import uuid
from factory.django import DjangoModelFactory
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save
import factory
from datetime import timezone
from core.models import (
    BaseModel,
    Schema,
    ReferenceItem,
    SchemaRef,
    DocumentationItem,
    Organization,
    Profile,
    PermanentURL
)

class ProfileFactory(DjangoModelFactory):
    class Meta: 
        model = Profile

    user = factory.SubFactory('tests.factories.UserFactory', profile=None)


@factory.django.mute_signals(post_save)
class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Faker('user_name')
    email = factory.Faker('email')
    password = factory.django.Password('testpassword')
    profile = factory.RelatedFactory(
        ProfileFactory,
        factory_related_name='user',
    )


class BaseModelFactory(DjangoModelFactory):
    created_by = factory.SubFactory(UserFactory)


class OrganizationFactory(BaseModelFactory):
    class Meta:
        model = Organization

    name = factory.Faker('company')
    slug = factory.Sequence(lambda n: f'orgslug-{n}')


class OrganizationProfileFactory(ProfileFactory):
    organization = factory.SubFactory(OrganizationFactory)


class OrganizationUserFactory(UserFactory):
    profile = factory.RelatedFactory(
        OrganizationProfileFactory,
        factory_related_name='user',
    )


class SchemaFactory(BaseModelFactory):
    class Meta:
         model = Schema
    
    name = factory.Faker('catch_phrase')
    published_at = factory.Faker("past_datetime", tzinfo=timezone.utc)


class OrganizationSchemaFactory(SchemaFactory):
    created_by = factory.SubFactory(OrganizationUserFactory)


class ReferenceItemFactory(BaseModelFactory):
    class Meta:
        model = ReferenceItem

    url = factory.Faker('url')


class SchemaRefFactory(ReferenceItemFactory):
    class Meta:
        model = SchemaRef

    schema = factory.SubFactory(SchemaFactory)


class OrganizationSchemaRefFactory(SchemaRefFactory):
    schema = factory.SubFactory(OrganizationSchemaFactory)
    created_by = factory.LazyAttribute(lambda instance: instance.schema.created_by)    
        

class DocumentationItemFactory(ReferenceItemFactory):
    class Meta:
        model = DocumentationItem

    name = factory.Faker('catch_phrase')
    description = factory.Faker('paragraph')
    schema = factory.SubFactory(SchemaFactory)
    role = factory.Iterator(DocumentationItem.DocumentationItemRole.values)
    format = factory.Iterator(DocumentationItem.DocumentationItemFormat.values)


class PermanentURLFactory(DjangoModelFactory):
    """
    By default, Permanent URLs will be UUIDs.
    You can pass link_type="organization" or link_type="email"
    to override, but then you must also include a suffix.
    """
    class Meta:
        model = PermanentURL

    suffix = factory.Sequence(lambda n: f'permanentOrgUrlSuffix-{n}')
    link_type = 'uuid'

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        link_type = kwargs.pop('link_type', 'uuid')
        suffix = kwargs.pop('suffix', None)
        content_object=kwargs.get('content_object')
        if link_type == 'uuid':
            return model_class.objects.create_from_uuid(
                created_by=content_object.created_by,
                uuid=uuid.uuid4(),
                **kwargs
            )
        elif link_type == 'email':
            return model_class.objects.create_from_email_suffix(
                created_by=content_object.created_by,
                suffix=suffix,
                **kwargs
            ) 
        elif link_type == 'organization':
            return model_class.objects.create_from_org_suffix(
                created_by=content_object.created_by,
                suffix=suffix,
                **kwargs
            )
