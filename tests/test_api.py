import logging

import pytest
from unittest.mock import patch
from django.test import Client, override_settings
from django.utils import timezone
from datetime import timedelta
import requests_mock
import json
from factories import (
    ProfileFactory,
    SchemaRefFactory,
    SchemaFactory,
    UserFactory
)
from core.models import Schema
from utils import assert_schema_matches_manifest


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
def test_api_key_allows_valid_api_key(api_client):
    url = "https://example.com/schema.json"
    id_value = "https://example.com/testid"
    content = f'{{"$id":"{id_value}"}}'
    with requests_mock.Mocker() as m:
        m.get(url, text=content)
        schema_ref = SchemaRefFactory.create(url=url)
        schema_ref.save()
        schema_ref.refresh_from_db()
        response = api_client.get(f'/api/find?id={id_value}')
        assert response.status_code == 200


@pytest.mark.django_db
@override_settings(HOURLY_API_REQUEST_LIMIT=2)
def test_api_key_enforces_rate_limit(api_client):
    url = "https://example.com/schema.json"
    id_value = "https://example.com/testid"
    content = f'{{"$id":"{id_value}"}}'
    with requests_mock.Mocker() as m:
        m.get(url, text=content)
        SchemaRefFactory.create(url=url)
        for _ in range(2):
            response = api_client.get(f'/api/find?id={id_value}')
            assert response.status_code == 200
        blocked_response = api_client.get(f'/api/find?id={id_value}')
        assert blocked_response.status_code == 429


# Make sure the rate limit is actually for the profile, not the API keys.
@pytest.mark.django_db
@override_settings(HOURLY_API_REQUEST_LIMIT=2)
def test_api_key_enforces_rate_limit_on_profile():
    client = Client()
    profile = ProfileFactory.create()
    raw_api_key = profile.set_new_api_key()
    url = "https://example.com/schema.json"
    id_value = "https://example.com/testid"
    content = f'{{"$id":"{id_value}"}}'
    with requests_mock.Mocker() as m:
        m.get(url, text=content)
        SchemaRefFactory.create(url=url)
        for _ in range(2):
            raw_api_key = profile.set_new_api_key()
            response = client.get(
                f'/api/find?id={id_value}',
                headers={'X-API-Key': raw_api_key}
            )
            assert response.status_code == 200
        raw_api_key = profile.set_new_api_key()
        blocked_response = client.get(
            f'/api/find?id={id_value}',
            headers={'X-API-Key': raw_api_key}
        )
        assert blocked_response.status_code == 429


@pytest.mark.django_db
def test_find_returns_matching_schema_ref_url(api_client):
    url = "https://example.com/schema.json"
    id_value = "https://example.com/testid"
    content = f'{{"$id":"{id_value}"}}'
    with requests_mock.Mocker() as m:
        m.get(url, text=content)
        SchemaRefFactory.create(url=url)
        response = api_client.get(
            f'/api/find?id={id_value}',
        )
        assert response.status_code == 200
        response_json = response.json()
        data = response_json.get('data')
        url = data.get('url')
        assert url == url
   

@pytest.mark.django_db
def test_find_returns_404s_for_matching_private_schemas(api_client):
    url = "https://example.com/schema.json"
    id_value = "https://example.com/testid"
    content = f'{{"$id":"{id_value}"}}'
    with requests_mock.Mocker() as m:
        m.get(url, text=content)
        schema_ref = SchemaRefFactory.create(url=url)
        schema_ref.schema.published_at = None
        schema_ref.schema.save()
        response = api_client.get(
            f'/api/find?id={id_value}',
        )
        assert response.status_code == 404


@pytest.mark.django_db
@override_settings(HOURLY_API_REQUEST_LIMIT=1)
def test_rate_limit_is_isolated_per_profile():
    # One profile hitting its limit must not affect a different profile.
    client = Client()
    profile_a = ProfileFactory.create()
    profile_b = ProfileFactory.create()
    key_a = profile_a.set_new_api_key()
    key_b = profile_b.set_new_api_key()

    mock_url = "https://example.com/schema.json"
    mock_id_value = "https://example.com/mockid"
    mock_content = f'{{"$id":"{mock_id_value}"}}'
    with requests_mock.Mocker() as m:
        m.get(mock_url, text=mock_content)
        SchemaRefFactory.create(url=mock_url)

        # Profile A burns its quota.
        assert client.get(
            f'/api/find?id={mock_id_value}',
            headers={'X-API-Key': key_a},
        ).status_code == 200
        assert client.get(
            f'/api/find?id={mock_id_value}',
            headers={'X-API-Key': key_a},
        ).status_code == 429

        # Profile B is untouched.
        assert client.get(
            f'/api/find?id={mock_id_value}',
            headers={'X-API-Key': key_b},
        ).status_code == 200


@pytest.mark.django_db
def test_api_fails_open_when_rate_limiter_unavailable(api_client, caplog):
    mock_url = "https://example.com/schema.json"
    mock_id_value = "https://example.com/mockid"
    mock_content = f'{{"$id":"{mock_id_value}"}}'
    with requests_mock.Mocker() as m:
        m.get(mock_url, text=mock_content)
        SchemaRefFactory.create(url=mock_url)

        fail_open = (True, "valkey_unavailable")
        with patch(
            "core.middleware.api_key_authentication_and_rate_limit.check_and_record_request",
            return_value=fail_open,
        ), caplog.at_level(logging.WARNING, logger="schemaindex"):
            response = api_client.get(f'/api/find?id={mock_id_value}')

    assert response.status_code == 200
    assert any(
        "api_rate_limit_failed_open" in record.getMessage()
        for record in caplog.records
    )


@pytest.mark.django_db
@override_settings(RATE_LIMIT_OBSERVABILITY=True)
def test_rate_limit_observability_logs_backend_and_decision(api_client, caplog):
    """When the flag is on, every gated request should produce both a
    backend-selection log and a decision log. We don't pin the backend
    to a specific value — locmem in tests, valkey in staging — only
    that the structured event was emitted.
    """
    mock_url = "https://example.com/schema.json"
    mock_id_value = "https://example.com/mockid"
    mock_content = f'{{"$id":"{mock_id_value}"}}'
    with requests_mock.Mocker() as m, \
            caplog.at_level(logging.INFO, logger="schemaindex"):
        m.get(mock_url, text=mock_content)
        SchemaRefFactory.create(url=mock_url)
        response = api_client.get(f'/api/find?id={mock_id_value}')

    assert response.status_code == 200
    messages = [r.getMessage() for r in caplog.records]
    assert any("rate_limit_backend_selected" in msg for msg in messages)
    assert any(
        "rate_limit_decision" in msg and "allowed=True" in msg
        for msg in messages
    )


@pytest.mark.django_db
@override_settings(RATE_LIMIT_OBSERVABILITY=True, HOURLY_API_REQUEST_LIMIT=1)
def test_rate_limit_observability_logs_blocked(api_client, caplog):
    mock_url = "https://example.com/schema.json"
    mock_id_value = "https://example.com/mockid"
    mock_content = f'{{"$id":"{mock_id_value}"}}'
    with requests_mock.Mocker() as m, \
            caplog.at_level(logging.INFO, logger="schemaindex"):
        m.get(mock_url, text=mock_content)
        SchemaRefFactory.create(url=mock_url)
        api_client.get(f'/api/find?id={mock_id_value}')
        blocked = api_client.get(f'/api/find?id={mock_id_value}')

    assert blocked.status_code == 429
    messages = [r.getMessage() for r in caplog.records]
    assert any("api_rate_limit_blocked" in msg for msg in messages)
    assert any(
        "rate_limit_decision" in msg and "allowed=False" in msg
        for msg in messages
    )


@pytest.mark.django_db
@override_settings(RATE_LIMIT_OBSERVABILITY=False)
def test_rate_limit_silent_when_observability_disabled(api_client, caplog):
    mock_url = "https://example.com/schema.json"
    mock_id_value = "https://example.com/mockid"
    mock_content = f'{{"$id":"{mock_id_value}"}}'
    with requests_mock.Mocker() as m, \
            caplog.at_level(logging.INFO, logger="schemaindex"):
        m.get(mock_url, text=mock_content)
        SchemaRefFactory.create(url=mock_url)
        api_client.get(f'/api/find?id={mock_id_value}')

    messages = [r.getMessage() for r in caplog.records]
    assert not any("rate_limit_backend_selected" in msg for msg in messages)
    assert not any("rate_limit_decision" in msg for msg in messages)


@pytest.mark.django_db
def test_create_schema_with_reference_items(api_client):
    definition_url = 'https://example.com/definition.json'
    readme_url = 'https://example.com/readme.md'
    implementation_url = 'https://example.com/implementation'
    manifest = {
        'name': 'Tock schema',
        'description': 'A test schema that is definitely real',
        'documents': {
            definition_url: {
                'type': 'definition',
                'name': 'Mock definition'
            },
            readme_url: {
                'type': 'documentation',
                'name': 'README.md',
                'role': 'readme',
                'format': 'markdown'
            },
            implementation_url: {
                'type': 'implementation',
                'isOpenSource': True
            }
        }
    }
    response = api_client.post(
        '/api/schemas',
        data=json.dumps(manifest),
        content_type='application/json'
    )
        
    assert response.status_code == 200
    response_json = response.json()
    data = response_json.get('data')
    schema_id = data.get('id')
    schema = Schema.objects.get(id=schema_id)
    assert_schema_matches_manifest(schema, manifest)


def test_create_rejects_non_json_payloads(api_client):
    response = api_client.post(
        '/api/schemas',
        data='not json',
        content_type='application/json'
    )
    assert response.status_code == 400


def test_create_rejects_non_manifest_payloads(api_client):
    response = api_client.post(
        '/api/schemas',
        data='{"not_a_manifest": true}',
        content_type='application/json'
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_create_prevents_publishing_schemas_with_existing_definition_urls(api_client):
    other_user = UserFactory.create()
    published_schema = SchemaFactory.create(created_by=other_user)
    url = 'https://example.com/definition.json'
    SchemaRefFactory.create(schema=published_schema, url=url)
    manifest = {
        'name': 'Test schema',
        'public': True,
        'documents': {
            url: {
                'type': 'definition',
            }
        }
    }
    response = api_client.post(
        '/api/schemas',
        data=json.dumps(manifest),
        content_type='application/json'
    )
    assert response.status_code == 400
    assert response.json()['error']['message'] == 'Validation Error'
    assert 'is already using one of the URL values used in this schema' in response.json()['error']['details'] 


@pytest.mark.django_db
def test_create_prevents_publishing_schemas_with_existing_id_values(api_client):
    other_user = UserFactory.create()
    published_schema = SchemaFactory.create(created_by=other_user)
    url = 'https://example.com/definition.json'
    id_value = 'https://example.com/definition'
    content = f'{{"$id":"{id_value}"}}'
    with requests_mock.Mocker() as m:
        m.get(url, text=content)
        SchemaRefFactory.create(schema=published_schema, url=url)
        manifest = {
            'name': 'Test schema',
            'public': True,
            'documents': {
                url: {
                    'type': 'definition',
                }
            }
        }
        response = api_client.post(
            '/api/schemas',
            data=json.dumps(manifest),
            content_type='application/json'
        )
        assert response.status_code == 400
        assert response.json()['error']['message'] == 'Validation Error'
        assert 'is already using one of the URL values used in this schema' in response.json()['error']['details'] 


@pytest.mark.django_db
def test_update_schema(api_client):
    schema = SchemaFactory.create(created_by=api_client.user, published_at=None)
    definition_url = 'https://example.com/definition.json'
    readme_url = 'https://example.com/readme.md'
    implementation_url = 'https://example.com/implementation'
    manifest = {
        'name': 'Test schema',
        'description': 'A test schema that is definitely real',
        'documents': {
            definition_url: {
                'type': 'definition',
                'name': 'Mock definition'
            },
            readme_url: {
                'type': 'documentation',
                'name': 'README.md',
                'role': 'readme',
                'format': 'markdown'
            },
            implementation_url: {
                'type': 'implementation',
                'isOpenSource': True
            }
        }
    }
    response = api_client.put(
        f'/api/schemas/{schema.id}',
        data=json.dumps(manifest),
        content_type='application/json'
    )
        
    assert response.status_code == 200
    response_json = response.json()
    data = response_json.get('data')
    schema_id = data.get('id')
    schema = Schema.objects.get(id=schema_id)
    assert_schema_matches_manifest(schema, manifest)


@pytest.mark.django_db
def test_update_404s_invalid_ids(api_client):
    response = api_client.put(
        '/api/schemas/404',
        data=json.dumps({
            'name': 'Mock schema',
            'documents': {
                'https://example.com/definition.json': {
                    'type': 'definition'
                }
            }
        })
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_update_rejects_non_json_payloads(api_client):
    schema = SchemaFactory.create(created_by=api_client.user)
    response = api_client.put(
        f'/api/schemas/{schema.id}',
        data='not json',
        content_type='application/json'
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_update_rejects_non_manifest_payloads(api_client):
    schema = SchemaFactory.create(created_by=api_client.user)
    response = api_client.put(
        f'/api/schemas/{schema.id}',
        data='{"not_a_manifest": true}',
        content_type='application/json'
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_update_404s_private_ids_created_by_other_user(api_client):
    other_user = UserFactory.create()
    schema = SchemaFactory.create(created_by=other_user, published_at=None)
    response = api_client.put(
        f'/api/schemas/{schema.id}',
        data=json.dumps({
            'name': 'Mock schema',
            'documents': {
                'https://example.com/definition.json': {
                    'type': 'definition'
                }
            }
        }),
        content_type='application/json'
    )
    assert response.status_code == 404
   

@pytest.mark.django_db
def test_update_403s_public_ids_created_by_other_user(api_client):
    other_user = UserFactory.create()
    schema = SchemaFactory.create(created_by=other_user)
    response = api_client.put(
        f'/api/schemas/{schema.id}',
        data=json.dumps({
            'name': 'Mock schema',
            'documents': {
                'https://example.com/definition.json': {
                    'type': 'definition'
                }
            }
        }),
        content_type='application/json'
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_update_prevents_unpublishing_schemas(api_client):
    schema = SchemaFactory.create(created_by=api_client.user)
    response = api_client.put(
        f'/api/schemas/{schema.id}',
        data=json.dumps({
            'name': 'Mock schema',
            'documents': {
                'https://example.com/definition.json': {
                    'type': 'definition'
                }
            }
        }),
        content_type='application/json'
    )
    assert response.status_code == 400
    assert response.json()['error']['message'] == 'Validation Error'
    assert 'Public schemas cannot be made private' in response.json()['error']['details']


@pytest.mark.django_db
def test_update_prevents_publishing_schemas_with_existing_definition_urls(api_client):
    schema = SchemaFactory.create(created_by=api_client.user)
    other_user = UserFactory.create()
    published_schema = SchemaFactory.create(created_by=other_user)
    url = 'https://example.com/definition.json'
    SchemaRefFactory.create(schema=published_schema, url=url)
    manifest = {
        'name': 'Test schema',
        'public': True,
        'documents': {
            url: {
                'type': 'definition',
            }
        }
    }
    response = api_client.put(
        f'/api/schemas/{schema.id}',
        data=json.dumps(manifest),
        content_type='application/json'
    )
    assert response.status_code == 400
    assert response.json()['error']['message'] == 'Validation Error'
    assert 'is already using one of the URL values used in this schema' in response.json()['error']['details'] 


@pytest.mark.django_db
def test_update_prevents_publishing_schemas_with_existing_id_values(api_client):
    schema = SchemaFactory.create(created_by=api_client.user)
    other_user = UserFactory.create()
    published_schema = SchemaFactory.create(created_by=other_user)
    url = 'https://example.com/definition.json'
    id_value = 'https://example.com/definition'
    content = f'{{"$id":"{id_value}"}}'
    with requests_mock.Mocker() as m:
        m.get(url, text=content)
        SchemaRefFactory.create(schema=published_schema, url=url)
        manifest = {
            'name': 'Test schema',
            'public': True,
            'documents': {
                url: {
                    'type': 'definition',
                }
            }
        }
        response = api_client.put(
            f'/api/schemas/{schema.id}',
            data=json.dumps(manifest),
            content_type='application/json'
        )
        assert response.status_code == 400
        assert response.json()['error']['message'] == 'Validation Error'
        assert 'is already using one of the URL values used in this schema' in response.json()['error']['details'] 


@pytest.mark.django_db
def test_update_preserves_published_at_when_updating_published_schema(api_client):
    published_at = timezone.now() - timedelta(days=10)
    schema = SchemaFactory.create(created_by=api_client.user, published_at=published_at)
    manifest = {
        'name': 'Test schema',
        'public': True,
        'documents': {
            'https://example.com/definiton.json': {
                'type': 'definition',
            }
        }
    }
    response = api_client.put(
        f'/api/schemas/{schema.id}',
        data=json.dumps(manifest),
        content_type='application/json'
    )
    assert response.status_code == 200
    schema.refresh_from_db()
    assert schema.published_at == published_at

