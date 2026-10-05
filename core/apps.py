from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        # Imported for its side effect of registering signal receivers,
        # e.g. creating a Profile for every new User.
        import core.signals  # noqa: F401

        from core.checks import check_local_only_hosts

        check_local_only_hosts()
