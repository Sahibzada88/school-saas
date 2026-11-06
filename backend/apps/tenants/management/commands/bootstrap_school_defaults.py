from django.core.management.base import BaseCommand

from apps.tenants.defaults import bootstrap_school
from apps.tenants.models import School, SchoolSettings


class Command(BaseCommand):
    help = "Create default session / grading scale / exam types / fee categories for schools that lack them (e.g. schools registered before these features existed)."

    def handle(self, *args, **options):
        count = 0
        for school in School.objects.all():
            SchoolSettings.objects.get_or_create(school=school)
            bootstrap_school(school)
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Defaults ensured for {count} school(s)."))
