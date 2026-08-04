# core/mcp/middleware.py
import logging
from core.mcp.sync_to_async_with_db_cleanup import sync_to_async_with_db_cleanup
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from core.models import APIKey
from core.middleware.rate_limit import check_and_record_request
from core.mcp.context import current_user

logger = logging.getLogger("schemaindex")

# TODO: dedupe from core/middleware/api_key_authentication.py

API_KEY_HEADER = "x-api-key"


class MCPAPIKeyAuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        api_key_header = request.headers.get(API_KEY_HEADER)

        if not api_key_header:
            return JSONResponse(
                status_code=401,
                content={
                    "status_code": 401,
                    "message": "Missing API Key",
                    "details": "Please include your API key with the X-API-Key header",
                },
            )

        # Safely wrap the synchronous ORM call
        api_key_obj = await sync_to_async_with_db_cleanup(APIKey.objects.get_from_key)(
            api_key_header
        )

        if not api_key_obj:
            return JSONResponse(
                status_code=401,
                content={
                    "status_code": 401,
                    "message": "Invalid API key",
                },
            )

        # Fetch profile and user safely in an async context
        @sync_to_async_with_db_cleanup
        def get_profile_and_user(key_obj):
            return key_obj.profile, key_obj.profile.user

        profile, user = await get_profile_and_user(api_key_obj)

        # Safely wrap the synchronous rate limiting logic
        allowed, reason = await sync_to_async_with_db_cleanup(check_and_record_request)(
            profile
        )

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "status_code": 429,
                    "message": "Too many requests",
                    "details": "You have exceeded your hourly request limit",
                },
            )

        if reason == "valkey_unavailable":
            logger.warning(
                "api_rate_limit_failed_open profile_id=%s path=%s",
                profile.id,
                request.url.path,
            )

        # Set the user in the ContextVar for this specific asyncio Task
        token = current_user.set(user)

        try:
            # Continue the request lifecycle
            response = await call_next(request)
            return response
        finally:
            # Clean up the context variable after the request finishes
            current_user.reset(token)
