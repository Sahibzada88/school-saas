from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.subscriptions.models import Plan

# DEVELOPMENT SEED DATA ONLY. Real plans and prices are created by the Super Admin in the UI/API.
SAMPLE_PLANS = [
    dict(slug="basic", name="Basic", sort_order=1, monthly_price=Decimal("5000"), max_students=200, max_teachers=20, max_classes=15,
         features=["Student & teacher management", "Attendance", "Basic reports"]),
    dict(slug="standard", name="Standard", sort_order=2, monthly_price=Decimal("10000"), max_students=600, max_teachers=60, max_classes=40,
         features=["Everything in Basic", "Exams & results", "Fee management"]),
    dict(slug="pro", name="Pro", sort_order=3, monthly_price=Decimal("20000"), max_students=None, max_teachers=None, max_classes=None,
         features=["Everything in Standard", "Unlimited students", "Priority support"]),
]


class Command(BaseCommand):
    help = "Create sample Basic/Standard/Pro plans for local development (skips plans that already exist)."

    def handle(self, *args, **options):
        for data in SAMPLE_PLANS:
            _, created = Plan.objects.get_or_create(slug=data["slug"], defaults={**data, "currency": "PKR", "description": "Development sample plan"})
            self.stdout.write(f"{'created' if created else 'exists '} {data['slug']}")
