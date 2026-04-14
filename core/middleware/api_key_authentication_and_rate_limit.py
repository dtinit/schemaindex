import time
from django.core.cache import cache
from django.http import JsonResponse
from core.models import APIKey
from django.conf import settings
from core.api_responses import ApiErrorResponse

API_KEY_HEADER = 'X-API-Key'

def get_profile_rate_limit_key(profile):
    return f'api_usage:sliding_log:{profile.id}'

class APIKeyAuthenticationAndRateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/api/"):
            return self.get_response(request)

        api_key_header = request.headers.get(API_KEY_HEADER)
        if not api_key_header:
            return ApiErrorResponse(
                status_code=401,
                message="Missing API Key",
                details=f"Please include your API key with the {API_KEY_HEADER} header"
            )
           
        api_key_obj = APIKey.objects.get_from_key(api_key_header)
        if not api_key_obj:
            return ApiErrorResponse(
                status_code=401,
                message="Invalid API key",
            )
            
        profile = api_key_obj.profile
        # For convenience, attach the user to the request
        request.user = profile.user

        if self.has_exceeded_rate_limit(profile):
             return ApiErrorResponse(
                status_code=429,
                message="Too many requests",
                details="You have exceed your hourly request limit"
            )

        return self.get_response(request)

    # Rate limits are tracked and applied per profile, not per API key.
    # This allows users to change API keys as needed,
    # but not as a way to circumvent rate limits.
    # 
    # This uses a sliding hourly window
    # rather than resetting at the beginning of every hour.
    # Note that it isn't atomic,
    # but it should be fine for our current usage and limits.
    def has_exceeded_rate_limit(self, profile):
        request_log_key = get_profile_rate_limit_key(profile)
        previous_request_log = cache.get(request_log_key, [])
        now = int(time.time())
        one_hour_ago = now - 3600
        # Filter out request logs from over an hour ago
        last_hour_request_log = [timestamp for timestamp in previous_request_log if timestamp > one_hour_ago]
        is_above_limit = len(last_hour_request_log) >= settings.HOURLY_API_REQUEST_LIMIT 
        if not is_above_limit:
            # Set the cache to our filtered list and allow it to expire in an hour.
            last_hour_request_log.append(now)
            cache.set(request_log_key, last_hour_request_log, timeout=3600)

        return is_above_limit
