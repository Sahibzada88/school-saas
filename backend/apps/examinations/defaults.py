from decimal import Decimal

from .models import GradeBand, GradingScale, ExamType

DEFAULT_BANDS = [
    ("A+", "90.00", "100.00", "4.00", "Outstanding", True),
    ("A", "80.00", "89.99", "3.50", "Excellent", True),
    ("B", "70.00", "79.99", "3.00", "Very good", True),
    ("C", "60.00", "69.99", "2.50", "Good", True),
    ("D", "50.00", "59.99", "2.00", "Satisfactory", True),
    ("F", "0.00", "49.99", "0.00", "Fail", False),
]


def create_defaults(school) -> None:
    """Called at school registration. Everything here is editable by the School Admin afterwards."""
    scale, created = GradingScale.objects.get_or_create(school=school, name="Standard", defaults={"is_default": True})
    if created:
        GradeBand.objects.bulk_create(
            [GradeBand(school=school, scale=scale, grade=g, min_percent=Decimal(lo), max_percent=Decimal(hi), gpa_points=Decimal(gpa), remark=r, is_pass=p)
             for g, lo, hi, gpa, r, p in DEFAULT_BANDS]
        )
    for name in ("Monthly Test", "Midterm", "Final"):
        if not ExamType.objects.filter(school=school, name=name).exists():
            ExamType.objects.create(school=school, name=name)
