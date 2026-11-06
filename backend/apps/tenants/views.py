import base64

from django.http import Http404, HttpResponse
from rest_framework.exceptions import ValidationError

from apps.accounts.roles import P
from apps.core.responses import success_response
from apps.core.viewsets import TenantAPIView

from .dashboard import build_school_dashboard
from .serializers import SchoolProfileSerializer
from .services import SchoolService


class SchoolProfileView(TenantAPIView):
    """/api/v1/school/profile/ : the caller's own school (no id in the URL, so no cross-tenant access is possible)."""

    required_permission = P.SCHOOL_SETTINGS

    def get(self, request):
        return success_response(SchoolProfileSerializer(self.get_school()).data, message="")

    def patch(self, request):
        school = self.get_school()
        serializer = SchoolProfileSerializer(school, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if not serializer.validated_data:
            raise ValidationError({"non_field_errors": ["No changes provided."]})
        SchoolService.update_profile(
            school=school, actor=request.user, data=serializer.validated_data, request=request
        )
        return success_response(SchoolProfileSerializer(school).data, message="School profile updated.")


class SchoolDashboardView(TenantAPIView):
    required_permission = P.SCHOOL_DASHBOARD

    def get(self, request):
        return success_response(build_school_dashboard(self.get_school()), message="")


class SchoolImageView(TenantAPIView):
    """GET /api/v1/school/images/{id}/ : serves a stored image. Scoped to the caller's school (404 otherwise), private
    caching, ETag so unchanged photos cost a 304."""

    required_permission = P.IMAGES_VIEW

    def get(self, request, image_id):
        from .models import ImageAsset

        asset = ImageAsset.objects.filter(school=self.get_school(), pk=image_id).first()
        if asset is None:
            raise Http404
        etag = f'"{asset.sha256}"'
        if request.headers.get("If-None-Match") == etag:
            response = HttpResponse(status=304)
        else:
            response = HttpResponse(base64.b64decode(asset.data_base64), content_type=asset.mime_type)
        response["ETag"] = etag
        response["Cache-Control"] = "private, max-age=86400"
        response["X-Content-Type-Options"] = "nosniff"
        return response
