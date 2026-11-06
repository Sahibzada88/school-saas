from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied

from apps.academics.models import Enrollment, SchoolClass, TeacherAssignment
from apps.accounts.roles import P, Role
from apps.audit_logs.actions import AuditAction
from apps.audit_logs.services import AuditService
from apps.core.fields import TenantScopedRelatedField
from apps.core.responses import success_response
from apps.core.viewsets import TenantModelViewSet
from apps.students.models import Student
from apps.students.scope import visible_students

from .models import Announcement, AnnouncementAudience as A, AnnouncementRead

STAFF_ROLES = {Role.SCHOOL_ADMIN, Role.TEACHER, Role.ACCOUNTANT, Role.RECEPTIONIST}


def taught_class_ids(user):
    return TeacherAssignment.objects.filter(school=user.school, teacher__user=user, session__is_current=True).values("section__school_class_id")


def family_class_ids(user):
    students = visible_students(user, Student.objects.filter(school=user.school))
    return Enrollment.objects.filter(student__in=students, session__is_current=True).values("school_class_id")


def visible_announcements(user, queryset):
    """Audience filtering at read time. Admin sees everything (including expired); others only live, targeted posts."""
    if user.role == Role.SCHOOL_ADMIN:
        return queryset
    now = timezone.now()
    queryset = queryset.filter(published_at__lte=now).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    audience = Q(audience=A.ALL)
    if user.role in STAFF_ROLES:
        audience |= Q(audience=A.STAFF)
    if user.role == Role.TEACHER:
        audience |= Q(audience=A.TEACHERS) | Q(audience=A.CLASS, school_class_id__in=taught_class_ids(user))
    elif user.role == Role.PARENT:
        audience |= Q(audience=A.PARENTS) | Q(audience=A.CLASS, school_class_id__in=family_class_ids(user))
    elif user.role == Role.STUDENT:
        audience |= Q(audience=A.STUDENTS) | Q(audience=A.CLASS, school_class_id__in=family_class_ids(user))
    return queryset.filter(audience)


class AnnouncementSerializer(serializers.ModelSerializer):
    school_class = TenantScopedRelatedField(queryset=SchoolClass.objects.all(), required=False, allow_null=True)
    class_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    is_read = serializers.BooleanField(read_only=True)
    published_at = serializers.DateTimeField(required=False)

    class Meta:
        model = Announcement
        fields = ("id", "title", "body", "audience", "school_class", "class_name", "is_pinned", "published_at", "expires_at", "created_by_name", "is_read", "created_at")
        read_only_fields = ("id", "class_name", "created_by_name", "is_read", "created_at")

    def get_class_name(self, obj):
        return obj.school_class.name if obj.school_class_id else None

    def get_created_by_name(self, obj):
        return obj.created_by.full_name if obj.created_by_id else None

    def validate(self, attrs):
        audience = attrs.get("audience", getattr(self.instance, "audience", A.ALL))
        school_class = attrs.get("school_class", getattr(self.instance, "school_class", None))
        if audience == A.CLASS and school_class is None:
            raise serializers.ValidationError({"school_class": ["Choose the class this announcement is for."]})
        if audience != A.CLASS:
            attrs["school_class"] = None
        expires, published = attrs.get("expires_at"), attrs.get("published_at")
        if expires and published and expires <= published:
            raise serializers.ValidationError({"expires_at": ["The expiry must be after the publish time."]})
        return attrs


class AnnouncementViewSet(TenantModelViewSet):
    """/api/v1/school/announcements/ : notice board. Admin posts to any audience; teachers only to their own classes."""

    queryset = Announcement.objects.select_related("school_class", "created_by")
    serializer_class = AnnouncementSerializer
    view_permission = P.ANNOUNCEMENTS_VIEW
    manage_permission = P.ANNOUNCEMENTS_CREATE
    permission_map = {
        "list": P.ANNOUNCEMENTS_VIEW, "retrieve": P.ANNOUNCEMENTS_VIEW, "create": P.ANNOUNCEMENTS_CREATE,
        "partial_update": P.ANNOUNCEMENTS_CREATE, "destroy": P.ANNOUNCEMENTS_CREATE, "read": P.ANNOUNCEMENTS_VIEW,
        "unread_count": P.ANNOUNCEMENTS_VIEW,
    }
    search_fields = ("title", "body")

    def scope_queryset(self, queryset):
        return visible_announcements(self.request.user, queryset)

    def get_queryset(self):
        queryset = super().get_queryset().annotate(
            is_read=Exists(AnnouncementRead.objects.filter(announcement=OuterRef("pk"), user=self.request.user))
        )
        return queryset.order_by("-is_pinned", "-published_at")

    def _check_teacher_rules(self, audience, school_class, instance=None):
        user = self.request.user
        if user.role == Role.SCHOOL_ADMIN:
            return
        if audience != A.CLASS or school_class is None or not taught_class_ids(user).filter(section__school_class_id=school_class.id).exists():
            raise PermissionDenied("Teachers can only post announcements to classes they teach.")
        if instance is not None and instance.created_by_id != user.id:
            raise PermissionDenied("You can only change your own announcements.")

    def perform_create(self, serializer):
        data = serializer.validated_data
        self._check_teacher_rules(data.get("audience", A.ALL), data.get("school_class"))
        school = self.get_school()
        announcement = serializer.save(school=school, created_by=self.request.user, published_at=data.get("published_at") or timezone.now())
        AuditService.record(
            AuditAction.ANNOUNCEMENT_CREATED, actor=self.request.user, school=school, entity_type="announcement", entity_id=announcement.id,
            description=f"Posted announcement '{announcement.title}' ({announcement.audience})", request=self.request,
        )

    def perform_update(self, serializer):
        instance = serializer.instance
        data = serializer.validated_data
        self._check_teacher_rules(data.get("audience", instance.audience), data.get("school_class", instance.school_class), instance)
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        self._check_teacher_rules(instance.audience, instance.school_class, instance)
        super().perform_destroy(instance)

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        announcement = self.get_object()
        AnnouncementRead.objects.get_or_create(school=announcement.school, announcement=announcement, user=request.user, defaults={"read_at": timezone.now()})
        return success_response(None, message="")

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        queryset = self.get_queryset().filter(is_read=False)
        return success_response({"count": queryset.count()}, message="")
