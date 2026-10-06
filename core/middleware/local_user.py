from asgiref.sync import sync_to_async
from django.conf import settings
from django.utils.functional import SimpleLazyObject

from core.local_user import get_local_user


class LocalUserMiddleware:
    """
    When ENABLE_ACCOUNTS is False, run every request as
    the built-in local superuser. When ENABLE_ACCOUNTS is True,
    this does nothing and AuthenticationMiddleware's user is
    left in place.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.ENABLE_ACCOUNTS:
            request.user = SimpleLazyObject(get_local_user)
            request.auser = sync_to_async(get_local_user)
        return self.get_response(request)
