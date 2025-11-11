import pytest
import requests_mock
from tests.factories import SchemaFactory, UserFactory, SchemaRefFactory
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


@pytest.mark.django_db
def test_published_schemas_listed():
    schema = SchemaFactory()
    client = Client()
    response = client.get('/')
    assert response.status_code == 200
    assert schema.name in str(response.content)


@pytest.mark.django_db
def test_private_schemas_not_listed():
    schema = SchemaFactory(published_at=None)
    client = Client()
    response = client.get('/')
    assert response.status_code == 200
    assert schema.name not in str(response.content)


@pytest.mark.django_db
def test_private_schemas_with_duplicate_urls_cannot_be_published():
    public_schema = SchemaFactory()
    public_schema_ref = SchemaRefFactory(schema=public_schema)
    private_schema = SchemaFactory(published_at=None)
    private_schema_ref = SchemaRefFactory(schema=private_schema, url=public_schema_ref.url)
    client = Client()
    client.force_login(private_schema.created_by)
    get_response = client.get(f'/manage/schema/{private_schema.id}/publish')
    assert get_response.status_code == 200
    assert "Schema definition already in use" in str(get_response.content)
    post_response = client.post(f'/manage/schema/{private_schema.id}/publish')
    assert post_response.status_code == 403
    assert private_schema.published_at == None


@pytest.mark.django_db
def test_private_schemas_with_new_urls_can_be_published():
    schema = SchemaFactory(published_at=None)
    schema_ref = SchemaRefFactory(schema=schema)
    client = Client()
    client.force_login(schema.created_by)
    get_response = client.get(f'/manage/schema/{schema.id}/publish')
    assert get_response.status_code == 200
    assert "Schema definition already in use" not in str(get_response.content)
    with requests_mock.Mocker() as m:
        m.get(schema_ref.url, text='{}')
        post_response = client.post(f'/manage/schema/{schema.id}/publish', follow=True)
        assert post_response.status_code == 200
    
    schema.refresh_from_db()
    assert schema.published_at != None

