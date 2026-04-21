import pytest
from django.test import Client, override_settings
from factories import ProfileFactory, SchemaRefFactory
import requests_mock
import json

def test_api_requires_key_header():
    client = Client()
    response = client.get('/api/find')
    assert response.status_code == 401


def test_api_requires_valid_api_key():
    client = Client()
    response = client.get(
        '/api/find',
        headers={'X-API-Key': 'invalid key'}
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_api_key_allows_valid_api_key():
    client = Client()
    profile = ProfileFactory.create()
    raw_api_key = profile.set_new_api_key()
    mock_url = "https://example.com/schema.json"
    mock_id_value = "https://example.com/mockid"
    mock_content = f'{{"$id":"{mock_id_value}"}}'
    with requests_mock.Mocker() as m:
        m.get(mock_url, text=mock_content)
        schema_ref = SchemaRefFactory.create(url=mock_url)
        schema_ref.save()
        schema_ref.refresh_from_db()
        response = client.get(
            f'/api/find?id={mock_id_value}',
            headers={'X-API-Key': raw_api_key}
        )
        assert response.status_code == 200


@pytest.mark.django_db
@override_settings(HOURLY_API_REQUEST_LIMIT=2)
def test_api_key_enforces_rate_limit():
    client = Client()
    profile = ProfileFactory.create()
    raw_api_key = profile.set_new_api_key()
    mock_url = "https://example.com/schema.json"
    mock_id_value = "https://example.com/mockid"
    mock_content = f'{{"$id":"{mock_id_value}"}}'
    with requests_mock.Mocker() as m:
        m.get(mock_url, text=mock_content)
        schema_ref = SchemaRefFactory.create(url=mock_url)
        for _ in range(2):
            response = client.get(
                f'/api/find?id={mock_id_value}',
                headers={'X-API-Key': raw_api_key}
            )
            assert response.status_code == 200
        blocked_response = client.get(
            f'/api/find?id={mock_id_value}',
            headers={'X-API-Key': raw_api_key}
        )
        assert blocked_response.status_code == 429


# Make sure the rate limit is actually for the profile, not the API keys.
@pytest.mark.django_db
@override_settings(HOURLY_API_REQUEST_LIMIT=2)
def test_api_key_enforces_rate_limit_on_profile():
    client = Client()
    profile = ProfileFactory.create()
    raw_api_key = profile.set_new_api_key()
    mock_url = "https://example.com/schema.json"
    mock_id_value = "https://example.com/mockid"
    mock_content = f'{{"$id":"{mock_id_value}"}}'
    with requests_mock.Mocker() as m:
        m.get(mock_url, text=mock_content)
        schema_ref = SchemaRefFactory.create(url=mock_url)
        for _ in range(2):
            raw_api_key = profile.set_new_api_key()
            response = client.get(
                f'/api/find?id={mock_id_value}',
                headers={'X-API-Key': raw_api_key}
            )
            assert response.status_code == 200
        raw_api_key = profile.set_new_api_key()
        blocked_response = client.get(
            f'/api/find?id={mock_id_value}',
            headers={'X-API-Key': raw_api_key}
        )
        assert blocked_response.status_code == 429


@pytest.mark.django_db
def test_find_returns_matching_schema_ref_url():
    client = Client()
    profile = ProfileFactory.create()
    raw_api_key = profile.set_new_api_key()
    mock_url = "https://example.com/schema.json"
    mock_id_value = "https://example.com/mockid"
    mock_content = f'{{"$id":"{mock_id_value}"}}'
    with requests_mock.Mocker() as m:
        m.get(mock_url, text=mock_content)
        schema_ref = SchemaRefFactory.create(url=mock_url)
        response = client.get(
            f'/api/find?id={mock_id_value}',
            headers={'X-API-Key': raw_api_key}
        )
        assert response.status_code == 200
        response_json = response.json()
        data = response_json.get('data')
        url = data.get('url')
        assert url == mock_url
   
