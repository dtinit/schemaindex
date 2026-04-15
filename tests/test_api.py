import pytest
from django.test import Client, override_settings
from factories import ProfileFactory

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
    response = client.get(
        '/api/find',
        headers={'X-API-Key': raw_api_key}
    )
    assert response.status_code == 200


@pytest.mark.django_db
@override_settings(HOURLY_API_REQUEST_LIMIT=2)
def test_api_key_enforces_rate_limit():
    client = Client()
    profile = ProfileFactory.create()
    raw_api_key = profile.set_new_api_key()
    for _ in range(2):
        response = client.get(
            '/api/find',
            headers={'X-API-Key': raw_api_key}
        )
        assert response.status_code == 200
    blocked_response = client.get(
        '/api/find',
        headers={'X-API-Key': raw_api_key}
    )
    assert blocked_response.status_code == 429


# Make sure the rate limit is actually for the profile, not the API keys.
@pytest.mark.django_db
@override_settings(HOURLY_API_REQUEST_LIMIT=2)
def test_api_key_enforces_rate_limit_on_profile():
    client = Client()
    profile = ProfileFactory.create()
    for _ in range(2):
        raw_api_key = profile.set_new_api_key()
        response = client.get(
            '/api/find',
            headers={'X-API-Key': raw_api_key}
        )
        assert response.status_code == 200
    raw_api_key = profile.set_new_api_key()
    blocked_response = client.get(
        '/api/find',
        headers={'X-API-Key': raw_api_key}
    )
    assert blocked_response.status_code == 429

