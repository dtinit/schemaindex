import importlib
import pytest
from django.core.cache import cache
from django.test import Client
from django.urls import clear_url_caches
import requests_mock as requests_mock_lib
from factories import ProfileFactory
import core.urls
import schemaindex.urls


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
        json={"message": "Default fallback response"},
        status_code=200,
    )
    return requests_mock


@pytest.fixture
def api_client(db):
    profile = ProfileFactory.create()
    api_key = profile.set_new_api_key()
    # Django requires CSRF tokens for "unsafe" HTTP methods
    # (POST/PUT/DELETE/etc) by default. To help verify that
    # our API views are exempt from CSRF checks as intended,
    # here we enable CSRF checks in the Django test client
    # used for API testing. Any API tests which use this
    # test client to test an API view that isn't exempt from CSRF
    # will fail, alerting developers of the problem.
    # Use the @csrf_exempt decorator for API views with "unsafe"
    # HTTP methods.
    client = Client(enforce_csrf_checks=True)
    client.defaults["HTTP_X_API_KEY"] = api_key
    client.user = profile.user
    return client


def _reload_urlconfs():
    # core.urls first, since schemaindex.urls includes it.
    importlib.reload(core.urls)
    importlib.reload(schemaindex.urls)
    clear_url_caches()


@pytest.fixture
def local_only_mode(settings):
    """
    Run a test in local-only mode (ENABLE_ACCOUNTS = False).

    The URLconfs check ENABLE_ACCOUNTS when they're imported, so
    overriding the setting alone isn't enough. They're reloaded
    here, and again on teardown once the setting is restored.
    """
    original = settings.ENABLE_ACCOUNTS
    settings.ENABLE_ACCOUNTS = False
    _reload_urlconfs()
    yield
    settings.ENABLE_ACCOUNTS = original
    _reload_urlconfs()
