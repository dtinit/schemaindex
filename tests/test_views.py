import pytest
import requests_mock
from tests.factories import (
    SchemaFactory, UserFactory, SchemaRefFactory,
    DocumentationItemFactory
)
from core.models import Schema, DocumentationItem
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
    # Undefined schemas aren't listed on the homepage
    SchemaRefFactory(schema=schema)
    client = Client()
    response = client.get('/')
    assert response.status_code == 200
    assert schema.name in str(response.content)


@pytest.mark.django_db
def test_private_schemas_not_listed():
    schema = SchemaFactory(published_at=None)
    # Make sure it has a definition so we know published_at
    # is the reason it's not showing up
    SchemaRefFactory(schema=schema)
    client = Client()
    response = client.get('/')
    assert response.status_code == 200
    assert schema.name not in str(response.content)


@pytest.mark.django_db
def test_published_schemas_filterable_by_language():
    json_schema = SchemaFactory()
    json_schema_ref = SchemaRefFactory(url="http://example.com/schema.json", schema=json_schema)
    xml_schema = SchemaFactory()
    xml_schema_ref = SchemaRefFactory(url="http://example.com/schema.xml", schema=xml_schema)
    client = Client()
    default_response = client.get('/')
    assert json_schema.name in str(default_response.content)
    assert xml_schema.name in str(default_response.content)
    json_filtered_response = client.get('/?specification_file_type=json')
    assert json_schema.name in str(json_filtered_response.content)
    assert xml_schema.name not in str(json_filtered_response.content)
    xml_filtered_response = client.get('/?specification_file_type=xml')
    assert json_schema.name not in str(xml_filtered_response.content)
    assert xml_schema.name in str(xml_filtered_response.content)


@pytest.mark.django_db
def test_published_schemas_filterable_by_documentation_item_role():
    rfc_schema = SchemaFactory()
    SchemaRefFactory(schema=rfc_schema)
    rfc_item = DocumentationItemFactory(
        schema=rfc_schema,
        role=DocumentationItem.DocumentationItemRole.RFC
    )
    w3c_schema = SchemaFactory()
    SchemaRefFactory(schema=w3c_schema)
    w3c_item = DocumentationItemFactory(
        schema=w3c_schema,
        role=DocumentationItem.DocumentationItemRole.W3C
    )
    client = Client()
    default_response = client.get('/')
    assert rfc_schema.name in str(default_response.content)
    assert w3c_schema.name in str(default_response.content)
    rfc_filtered_response = client.get(f'/?documentation_role={DocumentationItem.DocumentationItemRole.RFC.value}')
    assert rfc_schema.name in str(rfc_filtered_response.content)
    assert w3c_schema.name not in str(rfc_filtered_response.content)
    w3c_filtered_response = client.get(f'/?documentation_role={DocumentationItem.DocumentationItemRole.W3C.value}')
    assert rfc_schema.name not in str(w3c_filtered_response.content)
    assert w3c_schema.name in str(w3c_filtered_response.content)


@pytest.mark.django_db
def test_published_schemas_searchable_by_name():
    matching_schema = SchemaFactory(name="Matching Schema")
    SchemaRefFactory(schema=matching_schema)
    other_schema = SchemaFactory(name="Other Schema")
    SchemaRefFactory(schema=other_schema)
    client = Client()
    default_response = client.get('/')
    assert matching_schema.name in str(default_response.content)
    assert other_schema.name in str(default_response.content)
    searched_response = client.get('/?search_query=matching')
    assert matching_schema.name in str(searched_response.content)
    assert other_schema.name not in str(searched_response.content)


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


@pytest.mark.django_db
def test_private_schemas_can_be_deleted():
    schema = SchemaFactory(published_at=None)
    client = Client()
    client.force_login(schema.created_by)
    get_response = client.get(f'/manage/schema/{schema.id}/delete')
    assert get_response.status_code == 200
    post_response = client.post(f'/manage/schema/{schema.id}/delete', follow=True)
    assert post_response.status_code == 200
    assert not Schema.objects.filter(id=schema.id).exists()


@pytest.mark.django_db
def test_published_schemas_cannot_be_deleted():
    schema = SchemaFactory()
    client = Client()
    client.force_login(schema.created_by)
    get_response = client.get(f'/manage/schema/{schema.id}/delete')
    assert get_response.status_code == 403
    post_response = client.post(f'/manage/schema/{schema.id}/delete', follow=True)
    assert post_response.status_code == 403
    assert Schema.objects.filter(id=schema.id).exists()
                        
