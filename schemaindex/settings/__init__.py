import os

# If schemaindex/settings/personal.py exists,
# it should be the default settings module.
# Otherwise, use schemaindex/settings/development.py.
# Set DJANGO_SETTINGS_MODULE to override this behavior.

if os.path.exists(os.path.join(os.path.dirname(__file__), "personal.py")):
    from .personal import *
else:
    from .development import *
