import pytest
import requests.exceptions
import requests_mock
from unittest.mock import patch
from django.contrib.messages import get_messages
from django.urls import reverse
from core.models import SchemaRef
from factories import SchemaRefFactory


def run_refresh_id_values(admin_client, schema_refs):
    return admin_client.post(
        reverse("admin:core_schemaref_changelist"),
        {
            "action": "refresh_id_values",
            "_selected_action": [schema_ref.id for schema_ref in schema_refs],
        },
    )


def get_message_texts(response):
    return [str(message) for message in get_messages(response.wsgi_request)]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/schema.json",
        "https://example.com/schema.json?ref=main",
    ],
)
def test_refresh_id_values_reparses_id_value_from_fresh_content(admin_client, url):
    new_id_value = "https://example.com/new_id"
    with requests_mock.Mocker() as m:
        m.get(url, text='{"$id":"https://example.com/old_id"}')
        schema_ref = SchemaRefFactory.create(url=url)
        # Cache the old content under the SchemaRef's real cache key
        schema_ref.get_content()
        original_updated_at = SchemaRef.objects.get(id=schema_ref.id).updated_at
        m.get(url, text=f'{{"$id":"{new_id_value}"}}')
        response = run_refresh_id_values(admin_client, [schema_ref])
    schema_ref.refresh_from_db()
    assert schema_ref.id_value == new_id_value
    assert schema_ref.updated_at == original_updated_at
    assert any(
        message.startswith("Finished") for message in get_message_texts(response)
    )


@pytest.mark.django_db
@patch("core.models.time.sleep", return_value=None)
def test_refresh_id_values_keeps_id_value_when_fetch_fails(mock_sleep, admin_client):
    url = "https://example.com/schema.json"
    id_value = "https://example.com/id"
    with requests_mock.Mocker() as m:
        m.get(url, text=f'{{"$id":"{id_value}"}}')
        schema_ref = SchemaRefFactory.create(url=url)
        m.get(url, exc=requests.exceptions.ConnectionError)
        response = run_refresh_id_values(admin_client, [schema_ref])
    schema_ref.refresh_from_db()
    assert schema_ref.id_value == id_value
    assert any(str(schema_ref.id) in message for message in get_message_texts(response))
