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

"""
To avoid various complexities with trying to run the MCP server *inside* our Django app,
we run it *alongside* Django, inside a small Starlette app which mostly just routes requests.

Our full ASGI application looks something like this:


      incoming requests
             |
             |
             v
    [Parent Starlette app]
       |              |
       |              |
    requests       everything
    to /mcp*         else
       |              |
       |              |
       v              v
  [MCP server]---->[Django]
               ^
               |
    (the MCP server uses Django models
    to interact with the Django database)

"""


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
    from mcp.server.transport_security import TransportSecuritySettings  # noqa: E402

    # Create a lifespan context manager to run the session manager
    # At time of writing, MCP requires the lifespan protocol but Daphne doesn't support it,
    # which is why we must use uvicorn.
    # https://github.com/django/daphne/issues/264
    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette):
        async with mcp.session_manager.run():
            yield

    mcp_app = mcp.streamable_http_app(
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            # The SDK docs recommend including both "<host>" (matches bare host)
            # and "<host>:*" (matches any port)
            allowed_hosts=settings.ALLOWED_HOSTS
            + [host + ":*" for host in settings.ALLOWED_HOSTS],
            allowed_origins=settings.CSRF_TRUSTED_ORIGINS,
        ),
    )

    # We mount the MCP server at "/mcp" but it requires its own "/" at its root,
    # making the actual url "/mcp/" (trailing slash) and causing "/mcp" (no trailing slash) to 404.
    # This tiny middleware just redirects the latter to the former.
    class MCPTrailingSlashMiddleware:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http":
                if scope.get("path") == "/mcp":
                    scope["path"] = "/mcp/"

            await self.app(scope, receive, send)

    # Use Starlette (which is bundled with mcp)
    # to route /mcp requests to the mcp server,
    # and anything else to Django
    application = Starlette(
        routes=[
            Mount("/mcp", app=mcp_app),
            Mount("/", app=django_app),
        ],
        middleware=[
            Middleware(MCPTrailingSlashMiddleware),
        ],
        lifespan=lifespan,
    )

    return application


application = create_application()
