import logging

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.shared.exceptions import MCPError

from core.mcp.sync_to_async_with_db_cleanup import sync_to_async_with_db_cleanup
from core.middleware.rate_limit import check_and_record_request

logger = logging.getLogger("schemaindex")

# JSON-RPC "server error" range (-32000..-32099); signals an over-quota caller.
RATE_LIMITED = -32000


async def enforce_rate_limit(ctx, call_next):
    access_token = get_access_token()
    if access_token is None or access_token.subject is None:
        return await call_next(ctx)

    # subject is the Django user id, stamped by DjangoOAuthToolkitTokenVerifier
    user_id = int(access_token.subject)

    allowed, reason = await sync_to_async_with_db_cleanup(check_and_record_request)(
        user_id
    )
    if not allowed:
        logger.info(
            "[MCP] rate limit exceeded user_id=%s method=%s",
            user_id,
            ctx.method,
        )
        raise MCPError(
            RATE_LIMITED,
            "Hourly request limit exceeded. Please try again later.",
        )
    if reason == "valkey_unavailable":
        logger.warning(
            "api_rate_limit_failed_open user_id=%s method=%s",
            user_id,
            ctx.method,
        )

    return await call_next(ctx)
