import logging

import pytest
from unittest.mock import patch
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


@pytest.mark.django_db
@override_settings(HOURLY_API_REQUEST_LIMIT=1)
def test_rate_limit_is_isolated_per_profile():
    # One profile hitting its limit must not affect a different profile
    client = Client()
    profile_a = ProfileFactory.create()
    profile_b = ProfileFactory.create()
    key_a = profile_a.set_new_api_key()
    key_b = profile_b.set_new_api_key()

    # Profile A burns its quota.
    assert client.get('/api/find', headers={'X-API-Key': key_a}).status_code == 200
    assert client.get('/api/find', headers={'X-API-Key': key_a}).status_code == 429

    # Profile B is untouched.
    assert client.get('/api/find', headers={'X-API-Key': key_b}).status_code == 200


@pytest.mark.django_db
def test_api_fails_open_when_rate_limiter_unavailable(caplog):
    client = Client()
    profile = ProfileFactory.create()
    raw_api_key = profile.set_new_api_key()

    fail_open = (True, "valkey_unavailable")
    with patch(
        "core.middleware.api_key_authentication_and_rate_limit.check_and_record_request",
        return_value=fail_open,
    ):
        with caplog.at_level(logging.WARNING, logger="schemaindex"):
            response = client.get('/api/find', headers={'X-API-Key': raw_api_key})

    assert response.status_code == 200
    assert any(
        "api_rate_limit_failed_open" in record.getMessage()
        for record in caplog.records
    )

