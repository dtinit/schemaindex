from contextvars import ContextVar


# Stores the authenticated Django User for the lifespan of a single async request.
# Because FastMCP abstracts away the HTTP transport layer, we cannot easily pass
# Starlette's `request` object down to @mcp.tool() or @mcp.resource() functions.
# This ContextVar allows our auth middleware to safely inject the user state per-task,
# preventing concurrent requests from overriding each other's authentication state.
current_user = ContextVar("current_user", default=None)
