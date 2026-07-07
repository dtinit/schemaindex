"""
ASGI config for schemaindex project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import contextlib
import os
from django.core.asgi import get_asgi_application
from django.conf import settings
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.middleware import Middleware

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "schemaindex.settings.development")


def create_application():
    django_app = get_asgi_application()

    # Serve static files in development
    if settings.DEBUG:
        from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler

        django_app = ASGIStaticFilesHandler(django_app)

    if not settings.ENABLE_MCP_SERVER:
        return django_app

    # These imports must run after Django initializes
    from core.mcp.server import mcp  # noqa: E402
    from core.mcp.api_key_authentication import MCPAPIKeyAuthenticationMiddleware  # noqa: E402

    # Create a lifespan context manager to run the session manager
    # At time of writing, MCP requires the lifespan protocol but Daphne doesn't support it,
    # which is why we must use uvicorn.
    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette):
        async with mcp.session_manager.run():
            yield

    # Wrap the FastMCP streamable app with the API key middleware
    mcp_app = mcp.streamable_http_app()
    mcp_app_with_auth = Starlette(
        routes=mcp_app.routes,
        middleware=[Middleware(MCPAPIKeyAuthenticationMiddleware)],
    )
    # Use Starlette (which is bundled with mcp)
    # to route /mcp requests to the mcp server,
    # and anything else to Django
    application = Starlette(
        routes=[
            Mount("/mcp", app=mcp_app_with_auth),
            Mount("/", app=django_app),
        ],
        lifespan=lifespan,
    )

    return application


application = create_application()
