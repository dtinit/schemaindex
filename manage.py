#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "schemaindex.settings.development")

    # Intercept runserver so we can use an ASGI server.
    #
    # Django supports Daphne natively, but at time of writing,
    # Daphne doesn't support the lifespan protocol, which is required by our MCP server.
    # See https://github.com/django/daphne/issues/264
    # and https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/daphne/
    if len(sys.argv) > 1 and sys.argv[1] == "runserver":
        import uvicorn

        # Default to port 8000, but allow overrides like `python manage.py runserver 8080`
        port = 8000
        if len(sys.argv) > 2:
            try:
                # Handle basic port passing
                port_arg = sys.argv[2]
                port = (
                    int(port_arg.split(":")[-1]) if ":" in port_arg else int(port_arg)
                )
            except ValueError:
                pass

        print(f"Starting Uvicorn development server at http://127.0.0.1:{port}/")
        print("Quit the server with CONTROL-C.")

        # We pass the app as an import string so uvicorn's auto-reload works
        uvicorn.run(
            "schemaindex.asgi:application",
            host="127.0.0.1",
            port=port,
            reload=True,
            reload_includes=["*.html", "*.css"],
        )
        return

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
