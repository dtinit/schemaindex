import logging

from django.conf import settings

from core.api.responses import ApiErrorResponse
from core.models import APIKey
from .rate_limit import check_and_record_request

logger = logging.getLogger("schemaindex")

API_KEY_HEADER = "X-API-Key"


def get_api_key(request):
    """
    Reads the API key from an "Authorization: Bearer <key>" header if present,
    otherwise falls back to an "X-API-Key" header.
    """
    scheme, _, key = request.headers.get("Authorization", "").partition(" ")
    api_key = key.strip()
    if scheme.lower() == "bearer" and api_key:
        return api_key
    return request.headers.get(API_KEY_HEADER)


class APIKeyAuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/api/"):
            return self.get_response(request)

        if not settings.ENABLE_ACCOUNTS:
            # LocalUserMiddleware should have already set
            # request.user to the local user.
            return self.get_response(request)

        api_key = get_api_key(request)
        if not api_key:
            return ApiErrorResponse(
                status_code=401,
                message="Missing API Key",
                details="Please include your API key with the header 'Authorization: Bearer <API key>'",
            )

        api_key_obj = APIKey.objects.get_from_key(api_key)
        if not api_key_obj:
            return ApiErrorResponse(
                status_code=401,
                message="Invalid API key",
            )

        profile = api_key_obj.profile
        # For convenience, attach the user to the request
        request.user = profile.user

        # The helper enforces the per-user sliding-hourly window
        # against shared Valkey state in staging/production. If Valkey
        # is unavailable at runtime, the helper fails open and returns
        # reason="valkey_unavailable"
        allowed, reason = check_and_record_request(request.user.id)
        if not allowed:
            return ApiErrorResponse(
                status_code=429,
                message="Too many requests",
                details="You have exceeded your hourly request limit",
            )
        if reason == "valkey_unavailable":
            logger.warning(
                "api_rate_limit_failed_open user_id=%s path=%s",
                request.user.id,
                request.path,
            )

        return self.get_response(request)
