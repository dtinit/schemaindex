import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger("schemaindex")

LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]", "testserver"}


def check_local_only_hosts():
    """
    Refuse to start in local-only mode (ENABLE_ACCOUNTS = False) if
    the server accepts requests for non-local hosts, since every request
    acts as a superuser in that mode.

    This runs from CoreConfig.ready() rather than Django's system check
    framework because gunicorn/uvicorn don't run system checks.
    """
    if settings.ENABLE_ACCOUNTS:
        return

    remote_hosts = [h for h in settings.ALLOWED_HOSTS if h not in LOCAL_HOSTS]
    if not remote_hosts:
        return

    if not settings.ALLOW_NONLOCAL_HOSTS_WITHOUT_ACCOUNTS:
        raise ImproperlyConfigured(
            "ENABLE_ACCOUNTS is False, but ALLOWED_HOSTS contains non-local "
            f"hosts ({', '.join(remote_hosts)}). Anyone who can reach this "
            "server would have full admin access. Enable accounts, restrict "
            "ALLOWED_HOSTS, or set ALLOW_NONLOCAL_HOSTS_WITHOUT_ACCOUNTS = True."
        )

    logger.warning(
        "Running without accounts on non-local hosts (%s); "
        "anyone who can reach this server has full admin access.",
        ", ".join(remote_hosts),
    )
