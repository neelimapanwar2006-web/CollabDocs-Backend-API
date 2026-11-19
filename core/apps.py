from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        # Importing signals here ensures the Document post_save receiver is registered.
        from . import signals  # noqa: F401
