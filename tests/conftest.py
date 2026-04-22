import pytest
from django.core.cache import cache
import requests_mock as requests_mock_lib
from factories import ProfileFactory


@pytest.fixture(autouse=True)
def clear_cache():
    """
    Clear the Django cache before and after each test.
    Prevents cached values from leaking between tests.
    """
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def fallback_get_request_mock(requests_mock):
    """
    Catch-all fallback for GET requsets
    """
    # This matches any URL (http/https) and any method (GET/POST/etc.)
    requests_mock.get(
        requests_mock_lib.ANY, 
        json={'message': 'Default fallback response'},
        status_code=200
    )
    return requests_mock

@pytest.fixture
def api_client(client, db):
    profile = ProfileFactory.create()
    api_key = profile.set_new_api_key()
    client.defaults['HTTP_X_API_KEY'] = api_key 
    return client
