from .models import FeeCategory

DEFAULT_CATEGORIES = [("Tuition Fee", "TUI", True), ("Admission Fee", "ADM", False), ("Exam Fee", "EXM", False), ("Transport Fee", "TRN", True)]


def create_defaults(school) -> None:
    for name, code, recurring in DEFAULT_CATEGORIES:
        if not FeeCategory.objects.filter(school=school, code=code).exists():
            FeeCategory.objects.create(school=school, name=name, code=code, is_recurring=recurring)
