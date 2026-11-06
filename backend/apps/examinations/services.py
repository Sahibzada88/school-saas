from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.academics.models import Enrollment, EnrollmentStatus, TeacherAssignment
from apps.accounts.roles import Role
from apps.audit_logs.actions import AuditAction
from apps.audit_logs.services import AuditService
from apps.core.exceptions import Conflict

from .grading import band_for, percentage, q2, rank_desc, validate_bands
from .models import Exam, ExamStatus, ExamSubject, GradeBand, Mark, ReportCard, ResultStatus

TOOK_EXAM = [EnrollmentStatus.ENROLLED, EnrollmentStatus.PROMOTED, EnrollmentStatus.REPEATED, EnrollmentStatus.GRADUATED]


class MarksService:
    @staticmethod
    def allowed_sections(user, exam_subject: ExamSubject):
        """None = every section (School Admin). Otherwise the set of section ids this teacher may enter marks for."""
        if user.role == Role.SCHOOL_ADMIN:
            return None
        if user.role != Role.TEACHER:
            raise PermissionDenied("You cannot enter marks.")
        sections = set(
            TeacherAssignment.objects.filter(
                school=user.school, teacher__user=user, session=exam_subject.exam.session,
                section__school_class=exam_subject.school_class,
            ).filter(Q(subject=exam_subject.subject) | Q(subject__isnull=True)).values_list("section_id", flat=True)
        )
        if not sections:
            raise PermissionDenied("You are not assigned to teach this subject for this class.")
        return sections

    @staticmethod
    def _enrollments(exam_subject: ExamSubject, sections):
        queryset = Enrollment.objects.filter(
            school=exam_subject.school, session=exam_subject.exam.session, school_class=exam_subject.school_class, status__in=TOOK_EXAM
        ).select_related("student", "section")
        return queryset if sections is None else queryset.filter(section_id__in=sections)

    @staticmethod
    def roster(*, user, exam_subject: ExamSubject) -> list[dict]:
        sections = MarksService.allowed_sections(user, exam_subject)
        marks = {m.student_id: m for m in Mark.objects.filter(exam_subject=exam_subject)}
        rows = []
        for e in MarksService._enrollments(exam_subject, sections).order_by("section__name", "roll_number", "student__first_name"):
            mark = marks.get(e.student_id)
            rows.append({
                "student": str(e.student_id), "student_name": e.student.full_name, "student_number": e.student.student_number,
                "section": e.section.name, "roll_number": e.roll_number,
                "obtained_marks": mark.obtained_marks if mark else None, "is_absent": mark.is_absent if mark else False,
                "remarks": mark.remarks if mark else "", "entered": mark is not None,
            })
        return rows

    @staticmethod
    @transaction.atomic
    def save(*, user, exam: Exam, exam_subject: ExamSubject, entries: list[dict]) -> int:
        if exam.status not in (ExamStatus.SCHEDULED, ExamStatus.MARKS_ENTRY):
            raise Conflict("Marks entry is not open for this exam.", code="marks_closed")
        sections = MarksService.allowed_sections(user, exam_subject)
        enrollments = {str(e.student_id): e for e in MarksService._enrollments(exam_subject, sections)}
        rows, clear, seen = [], [], set()
        for entry in entries:
            key = str(entry["student"])
            enrollment = enrollments.get(key)
            if enrollment is None:
                raise ValidationError({"entries": ["A student in the request is not in a class/section you may enter marks for."]})
            if key in seen:
                raise ValidationError({"entries": ["A student appears more than once."]})
            seen.add(key)
            obtained, absent = entry.get("obtained_marks"), entry.get("is_absent", False)
            if absent:
                obtained = None
            elif obtained is None:
                clear.append(enrollment.student_id)  # blank cell = clear the mark
                continue
            elif obtained < 0 or obtained > exam_subject.total_marks:
                raise ValidationError({"entries": [f"Marks must be between 0 and {exam_subject.total_marks} (student {enrollment.student.student_number})."]})
            rows.append(Mark(
                school=exam_subject.school, exam_subject=exam_subject, enrollment=enrollment, student_id=enrollment.student_id,
                obtained_marks=obtained, is_absent=absent, remarks=entry.get("remarks", ""), entered_by=user,
            ))
        Mark.objects.bulk_create(
            rows, update_conflicts=True, unique_fields=["exam_subject", "student"],
            update_fields=["obtained_marks", "is_absent", "remarks", "entered_by", "enrollment", "updated_at"],
        )
        if clear:
            Mark.objects.filter(exam_subject=exam_subject, student_id__in=clear).delete()
        if exam.status == ExamStatus.SCHEDULED:
            Exam.objects.filter(pk=exam.pk, status=ExamStatus.SCHEDULED).update(status=ExamStatus.MARKS_ENTRY, updated_at=timezone.now())
        return len(rows)


@dataclass
class StudentResult:
    enrollment: Enrollment
    lines: list = field(default_factory=list)
    total: Decimal = Decimal("0")
    obtained: Decimal = Decimal("0")
    percentage: Decimal = Decimal("0")
    grade: str = ""
    gpa: Decimal = Decimal("0")
    status: str = ResultStatus.FAIL
    missing: int = 0
    position_section: int | None = None
    position_class: int | None = None


class ResultService:
    @staticmethod
    def compute(exam: Exam, *, missing_as_absent: bool = True) -> list[StudentResult]:
        """Pure computation from live marks. Used for the preview and for publishing; nothing is stored here."""
        subjects = list(ExamSubject.objects.filter(exam=exam).select_related("subject"))
        by_class: dict = {}
        for s in subjects:
            by_class.setdefault(s.school_class_id, []).append(s)
        bands = list(exam.grading_scale.bands.all())
        marks = {(m.exam_subject_id, m.student_id): m for m in Mark.objects.filter(exam_subject__exam=exam)}
        enrollments = Enrollment.objects.filter(
            school=exam.school, session=exam.session, school_class_id__in=by_class.keys(), status__in=TOOK_EXAM
        ).select_related("student", "section", "school_class")

        results = []
        for enrollment in enrollments:
            result = StudentResult(enrollment=enrollment)
            all_pass = True
            for s in sorted(by_class[enrollment.school_class_id], key=lambda x: x.subject.name):
                mark = marks.get((s.id, enrollment.student_id))
                missing = mark is None
                absent = missing or mark.is_absent
                obtained = Decimal("0") if absent else (mark.obtained_marks or Decimal("0"))
                if missing:
                    result.missing += 1
                line_pass = (not absent) and obtained >= s.passing_marks
                all_pass = all_pass and line_pass
                line_band = band_for(percentage(obtained, s.total_marks), bands)
                result.lines.append({
                    "subject": s.subject.name, "code": s.subject.code, "total": str(s.total_marks), "obtained": str(obtained),
                    "passing": str(s.passing_marks), "grade": line_band.grade if line_band else "", "is_absent": absent,
                    "is_missing": missing, "is_pass": line_pass,
                })
                result.total += s.total_marks
                result.obtained += obtained
            result.percentage = percentage(result.obtained, result.total)
            band = band_for(result.percentage, bands)
            result.grade, result.gpa = (band.grade, band.gpa_points) if band else ("", Decimal("0"))
            result.status = ResultStatus.PASS if (all_pass and result.lines) else ResultStatus.FAIL
            results.append(result)

        for key_name, attr in (("section_id", "position_section"), ("school_class_id", "position_class")):
            groups: dict = {}
            for r in results:
                groups.setdefault(getattr(r.enrollment, key_name), {})[r.enrollment.student_id] = r.obtained
            ranks = {gid: rank_desc(scores) for gid, scores in groups.items()}
            for r in results:
                setattr(r, attr, ranks[getattr(r.enrollment, key_name)][r.enrollment.student_id])
        results.sort(key=lambda r: (r.enrollment.school_class.level_order, r.enrollment.section.name, r.position_section or 0))
        return results

    @staticmethod
    def serialize_preview(result: StudentResult) -> dict:
        e = result.enrollment
        return {
            "student": str(e.student_id), "student_name": e.student.full_name, "student_number": e.student.student_number,
            "class_name": e.school_class.name, "section_name": e.section.name, "roll_number": e.roll_number,
            "total_marks": str(result.total), "obtained_marks": str(result.obtained), "percentage": str(result.percentage),
            "grade": result.grade, "gpa": str(result.gpa), "result_status": result.status, "missing_marks": result.missing,
            "position_section": result.position_section, "position_class": result.position_class, "lines": result.lines,
        }


class ExamService:
    TRANSITIONS = {
        "schedule": ({ExamStatus.DRAFT}, ExamStatus.SCHEDULED),
        "open_marks": ({ExamStatus.SCHEDULED}, ExamStatus.MARKS_ENTRY),
        "archive": ({ExamStatus.PUBLISHED}, ExamStatus.ARCHIVED),
    }

    @staticmethod
    @transaction.atomic
    def transition(*, exam: Exam, action: str) -> Exam:
        allowed_from, target = ExamService.TRANSITIONS[action]
        if exam.status not in allowed_from:
            raise Conflict(f"An exam that is {exam.status.lower().replace('_', ' ')} cannot be moved to {target.lower().replace('_', ' ')}.", code="invalid_transition")
        if action == "schedule" and not exam.subjects.exists():
            raise Conflict("Add at least one exam subject before scheduling.", code="no_subjects")
        exam.status = target
        exam.save(update_fields=["status", "updated_at"])
        return exam

    @staticmethod
    @transaction.atomic
    def publish(*, exam: Exam, force: bool, actor, request) -> dict:
        if exam.status not in (ExamStatus.SCHEDULED, ExamStatus.MARKS_ENTRY, ExamStatus.PUBLISHED):
            raise Conflict("Only a scheduled exam (or an already published one, to recompute) can be published.", code="invalid_transition")
        results = ResultService.compute(exam)
        if not results:
            raise Conflict("There are no enrolled students for this exam's classes.", code="no_results")
        missing = sum(r.missing for r in results)
        if missing and not force:
            raise Conflict(f"{missing} mark(s) have not been entered. Enter them, or publish with force to count them as absent.", code="missing_marks")

        now = timezone.now()
        cards = [
            ReportCard(
                school=exam.school, exam=exam, student_id=r.enrollment.student_id, enrollment=r.enrollment,
                total_marks=r.total, obtained_marks=r.obtained, percentage=r.percentage, grade=r.grade, gpa=r.gpa,
                position_section=r.position_section, position_class=r.position_class, result_status=r.status,
                breakdown={
                    "lines": r.lines,
                    "grading": [{"grade": b.grade, "min": str(b.min_percent), "max": str(b.max_percent), "gpa": str(b.gpa_points)} for b in exam.grading_scale.bands.all()],
                },
                computed_at=now, published_at=now, is_published=True,
            )
            for r in results
        ]
        ReportCard.objects.bulk_create(
            cards, update_conflicts=True, unique_fields=["exam", "student"],
            update_fields=["enrollment", "total_marks", "obtained_marks", "percentage", "grade", "gpa", "position_section",
                           "position_class", "result_status", "breakdown", "computed_at", "published_at", "is_published", "updated_at"],
        )
        ReportCard.objects.filter(exam=exam).exclude(student_id__in=[r.enrollment.student_id for r in results]).delete()
        first_time = exam.status != ExamStatus.PUBLISHED
        exam.status, exam.published_at = ExamStatus.PUBLISHED, exam.published_at or now
        exam.save(update_fields=["status", "published_at", "updated_at"])
        AuditService.record(
            AuditAction.EXAM_PUBLISHED, actor=actor, school=exam.school, entity_type="exam", entity_id=exam.id,
            description=f"{'Published' if first_time else 'Recomputed'} results of {exam.name} for {len(results)} student(s)",
            metadata={"students": len(results), "missing": missing, "forced": force}, request=request,
        )
        return {"students": len(results), "missing_marks_counted_absent": missing}


class GradingService:
    @staticmethod
    @transaction.atomic
    def save_scale(*, scale, name=None, is_default=None, bands=None):
        if bands is not None:
            errors = validate_bands([dict(b) for b in bands])
            if errors:
                raise ValidationError({"bands": errors})
        if name is not None:
            scale.name = name
        if is_default:
            type(scale).objects.filter(school=scale.school, is_default=True).exclude(pk=scale.pk).update(is_default=False)
            scale.is_default = True
        elif is_default is False:
            scale.is_default = False
        scale.save()
        if bands is not None:
            scale.bands.all().delete()
            GradeBand.objects.bulk_create([GradeBand(school=scale.school, scale=scale, **dict(b)) for b in bands])
        return scale
