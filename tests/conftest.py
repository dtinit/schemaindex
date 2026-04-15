import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def clear_cache():
    """
    Clear the Django cache before and after each test.
    Prevents cached values from leaking between tests.
    """
    cache.clear()
    yield
    cache.clear()
