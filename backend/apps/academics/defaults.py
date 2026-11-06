from datetime import date

from .models import AcademicSession


def create_defaults(school) -> None:
    """A current academic session so a new school can enrol students immediately (editable afterwards)."""
    if AcademicSession.objects.filter(school=school).exists():
        return
    year = date.today().year
    AcademicSession.objects.create(school=school, name=str(year), start_date=date(year, 1, 1), end_date=date(year, 12, 31), is_current=True)
