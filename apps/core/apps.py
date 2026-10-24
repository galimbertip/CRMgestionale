from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = "Utenti e sistema"

    def ready(self):
        from . import ruoli

        post_migrate.connect(ruoli.post_migrate, dispatch_uid="gpverse_gruppi")
