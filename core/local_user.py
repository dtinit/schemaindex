from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password

LOCAL_USERNAME = "default_admin"


def get_local_user():
    """
    Return the built-in superuser that every request acts as in
    local-only mode (ENABLE_ACCOUNTS = False), creating it on first use.

    The post_save receiver in core/signals.py creates its Profile.
    """
    # Fail loudly if a caller attempts to get the local user
    # while ENABLE_ACCOUNTS is True
    if settings.ENABLE_ACCOUNTS:
        raise RuntimeError(
            "get_local_user() was called with ENABLE_ACCOUNTS on. The local "
            "user only exists in local-only mode."
        )

    user, _ = get_user_model().objects.get_or_create(
        username=LOCAL_USERNAME,
        defaults={
            "is_staff": True,
            "is_superuser": True,
            # An unusable password: this user can never log in with one.
            "password": make_password(None),
        },
    )
    return user
