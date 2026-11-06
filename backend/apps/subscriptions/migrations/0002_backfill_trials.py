from datetime import timedelta

from django.db import migrations
from django.utils import timezone

BACKFILL_TRIAL_DAYS = 7  # one-off backfill for schools registered before billing existed (Phases 2-3)


def backfill(apps, schema_editor):
    School = apps.get_model("tenants", "School")
    Subscription = apps.get_model("subscriptions", "Subscription")
    now = timezone.now()
    have = set(Subscription.objects.values_list("school_id", flat=True))
    Subscription.objects.bulk_create(
        [
            Subscription(
                school_id=school_id, status="TRIALING", trial_start=now,
                trial_end=now + timedelta(days=BACKFILL_TRIAL_DAYS),
            )
            for school_id in School.objects.values_list("id", flat=True)
            if school_id not in have
        ]
    )


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0001_initial")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
