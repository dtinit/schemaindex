import pytest
from django.core.cache import cache
from django.test import Client
from django.db import connection
import requests_mock as requests_mock_lib
from factories import ProfileFactory


@pytest.fixture(scope="session", autouse=True)
def force_terminate_db_connections(django_db_setup, django_db_blocker):
    """
    Hooks into pytest-django's teardown lifecycle.
    Guarantees that all background thread connections are killed
    before pytest tries to drop the test database.
    """
    yield

    with django_db_blocker.unblock():
        with connection.cursor() as cursor:
            db_name = connection.settings_dict["NAME"]
            cursor.execute(
                f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{db_name}'
                  AND pid <> pg_backend_pid();
                """
            )

        connection.close()


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
