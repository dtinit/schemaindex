import logging

from django.contrib.auth import get_user_model
from mcp.server import ServerRequestContext
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.context import CallNext, HandlerResult
from mcp.shared.exceptions import MCPError

from core.mcp.context import current_user
from core.mcp.sync_to_async_with_db_cleanup import sync_to_async_with_db_cleanup
from core.middleware.rate_limit import check_and_record_request

logger = logging.getLogger("schemaindex")
User = get_user_model()

# JSON-RPC "server error" range (-32000..-32099); signals an over-quota caller.
RATE_LIMITED = -32000

# Methods that count against the per-user hourly quota — the ones that touch the DB.
# Widen to "any request" (ctx.request_id is not None) to match the old middleware's
# count-every-request behavior.
RATE_LIMITED_METHODS = frozenset({"tools/call", "resources/read"})


@sync_to_async_with_db_cleanup
def _load_user_and_profile(user_id):
    user = User.objects.select_related("profile").get(pk=user_id)
    return user, user.profile


async def authenticate_and_rate_limit(
    ctx: ServerRequestContext, call_next: CallNext
) -> HandlerResult:
    access_token = get_access_token()
    if access_token is None or access_token.subject is None:
        return await call_next(ctx)

    # subject is the Django user id, stamped by DjangoOAuthToolkitTokenVerifier
    user, profile = await _load_user_and_profile(int(access_token.subject))

    if ctx.method in RATE_LIMITED_METHODS:
        allowed, reason = await sync_to_async_with_db_cleanup(check_and_record_request)(
            profile
        )
        if not allowed:
            logger.info(
                "[MCP] rate limit exceeded profile_id=%s method=%s",
                profile.id,
                ctx.method,
            )
            raise MCPError(
                RATE_LIMITED,
                "Hourly request limit exceeded. Please try again later.",
            )
        if reason == "valkey_unavailable":
            logger.warning(
                "api_rate_limit_failed_open profile_id=%s method=%s",
                profile.id,
                ctx.method,
            )

    reset = current_user.set(user)
    try:
        return await call_next(ctx)
    finally:
        current_user.reset(reset)
