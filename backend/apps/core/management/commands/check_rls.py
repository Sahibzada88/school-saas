from django.core.management.base import BaseCommand, CommandError

from apps.core.rls import tables_without_rls


class Command(BaseCommand):
    help = "Fail if any table in the public schema lacks Row Level Security (PostgreSQL only)."

    def handle(self, *args, **options):
        missing = tables_without_rls()
        if missing:
            raise CommandError("Tables without RLS: " + ", ".join(missing))
        self.stdout.write(self.style.SUCCESS("All public tables have RLS enabled."))
