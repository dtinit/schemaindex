import functools
from asgiref.sync import sync_to_async
from django.db import close_old_connections


def sync_to_async_with_db_cleanup(func=None, **kwargs):
    """
    A wrapper around sync_to_async that ensures database connections
    are safely closed before and after the synchronous function executes
    in the background thread pool.
    """

    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **inner_kwargs):
            close_old_connections()
            try:
                return f(*args, **inner_kwargs)
            finally:
                close_old_connections()

        return sync_to_async(wrapper, **kwargs)

    if func is None:
        return decorator
    return decorator(func)
