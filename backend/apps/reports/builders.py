from datetime import date
from decimal import Decimal

from django.db.models import Avg, Count, Max, Min, OuterRef, Q, Subquery, Sum

from apps.academics.models import Enrollment
from apps.examinations.models import ExamSubject, Mark
from apps.fees.models import InvoiceStatus, StudentInvoice
from apps.students.models import Student, StudentGuardian
from apps.students.scope import visible_students


def students_queryset(user, params):
    """Visible students with current class/section and the primary guardian, in one query (no N+1)."""
    current = Enrollment.objects.filter(student=OuterRef("pk"), session__is_current=True).order_by("-created_at")
    guardian = StudentGuardian.objects.filter(student=OuterRef("pk")).order_by("-is_primary", "created_at")
    queryset = visible_students(user, Student.objects.filter(school=user.school)).annotate(
        class_name=Subquery(current.values("school_class__name")[:1]),
        section_name=Subquery(current.values("section__name")[:1]),
        roll=Subquery(current.values("roll_number")[:1]),
        guardian_name=Subquery(guardian.values("guardian__first_name")[:1]),
        guardian_phone=Subquery(guardian.values("guardian__phone")[:1]),
    )
    if params.get("status"):
        queryset = queryset.filter(status=params["status"])
    if params.get("class"):
        queryset = queryset.filter(enrollments__school_class_id=params["class"], enrollments__session__is_current=True)
    if params.get("section"):
        queryset = queryset.filter(enrollments__section_id=params["section"], enrollments__session__is_current=True)
    return queryset.distinct().order_by("first_name", "last_name")


def outstanding(school, params, limit: int | None = None) -> dict:
    queryset = StudentInvoice.objects.filter(
        school=school, status__in=[InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID], balance__gt=0
    ).select_related("student", "enrollment__school_class", "enrollment__section")
    if params.get("class"):
        queryset = queryset.filter(enrollment__school_class_id=params["class"])
    if params.get("section"):
        queryset = queryset.filter(enrollment__section_id=params["section"])
    primary = StudentGuardian.objects.filter(student=OuterRef("student_id")).order_by("-is_primary", "created_at")
    queryset = queryset.annotate(g_first=Subquery(primary.values("guardian__first_name")[:1]), g_phone=Subquery(primary.values("guardian__phone")[:1]))
    totals = queryset.aggregate(total=Sum("balance"), count=Count("id"))
    today = date.today()
    ordered = queryset.order_by("due_date", "invoice_number")
    rows = [
        {
            "invoice_id": str(i.id), "invoice_number": i.invoice_number, "student_name": i.student.full_name,
            "student_number": i.student.student_number,
            "class_name": f"{i.enrollment.school_class.name}-{i.enrollment.section.name}" if i.enrollment_id else "",
            "period_label": i.period_label, "due_date": i.due_date.isoformat(), "balance": f"{i.balance:.2f}",
            "days_overdue": max(0, (today - i.due_date).days),
            "guardian_name": i.g_first or "", "guardian_phone": i.g_phone or "",
        }
        for i in (ordered[:limit] if limit else ordered)
    ]
    total = totals["total"] or Decimal("0")
    return {"rows": rows, "count": totals["count"], "total": f"{total:.2f}", "truncated": bool(limit and totals["count"] > limit)}


def students_summary(user) -> dict:
    queryset = visible_students(user, Student.objects.filter(school=user.school))
    by_status = {r["status"]: r["c"] for r in queryset.order_by().values("status").annotate(c=Count("id"))}
    by_gender = {r["gender"]: r["c"] for r in queryset.order_by().values("gender").annotate(c=Count("id"))}
    by_class = [
        {"class_name": r["school_class__name"], "section_name": r["section__name"], "count": r["c"]}
        for r in Enrollment.objects.filter(student__in=queryset, session__is_current=True, status="ENROLLED").order_by("school_class__level_order", "section__name")
        .values("school_class__name", "section__name", "school_class__level_order").annotate(c=Count("id"))
    ]
    return {"total": queryset.count(), "by_status": by_status, "by_gender": by_gender, "by_class": by_class}


def exam_analysis(exam) -> dict:
    subjects = []
    for es in ExamSubject.objects.filter(exam=exam).select_related("school_class", "subject").order_by("school_class__level_order", "subject__name"):
        marks = Mark.objects.filter(exam_subject=es)
        agg = marks.filter(is_absent=False, obtained_marks__isnull=False).aggregate(avg=Avg("obtained_marks"), high=Max("obtained_marks"), low=Min("obtained_marks"), n=Count("id"), passed=Count("id", filter=Q(obtained_marks__gte=es.passing_marks)))
        absent = marks.filter(is_absent=True).count()
        n = agg["n"] or 0
        subjects.append({
            "class_name": es.school_class.name, "subject": es.subject.name, "total_marks": str(es.total_marks), "entered": n + absent, "absent": absent,
            "average": None if agg["avg"] is None else f"{agg['avg']:.2f}", "highest": None if agg["high"] is None else str(agg["high"]),
            "lowest": None if agg["low"] is None else str(agg["low"]), "pass_rate": None if n == 0 else round(agg["passed"] * 100 / n, 2),
        })
    cards = exam.report_cards.all()
    total = cards.count()
    passed = cards.filter(result_status="PASS").count()
    return {"exam": exam.name, "status": exam.status, "students": total, "passed": passed, "pass_rate": None if total == 0 else round(passed * 100 / total, 2), "subjects": subjects}
