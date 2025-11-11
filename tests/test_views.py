import pytest
from tests.factories import SchemaFactory, UserFactory
from django.test import Client


@pytest.mark.django_db
def test_private_schemas_404_to_anonymous():
    schema = SchemaFactory(published_at=None)
    client = Client()
    response = client.get(f'/schemas/{schema.id}', follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_private_schemas_404_to_non_creators():
    schema = SchemaFactory(published_at=None)
    client = Client()
    client.force_login(UserFactory())
    response = client.get(f'/schemas/{schema.id}', follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_private_schemas_accessible_to_creators():
    schema = SchemaFactory(published_at=None)
    client = Client()
    client.force_login(schema.created_by)
    response = client.get(f'/schemas/{schema.id}', follow=True)
    assert response.status_code == 200
