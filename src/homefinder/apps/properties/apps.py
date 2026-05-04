from django.apps import AppConfig


class PropertiesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "homefinder.apps.properties"
    label = "properties"
    verbose_name = "Properties"

    def ready(self) -> None:
        from . import signals  # noqa: F401
