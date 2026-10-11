from django.apps import AppConfig


class GatewayConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gateway'
    verbose_name = 'Unified API gateway'

    def ready(self):
        from gateway import checks  # noqa: F401  (registers the system checks)
