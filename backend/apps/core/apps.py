from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"

    def ready(self):
        from django.db.models.signals import post_migrate

        from .rls import lockdown_after_migrate

        post_migrate.connect(lockdown_after_migrate, sender=self, dispatch_uid="core.rls_lockdown")
