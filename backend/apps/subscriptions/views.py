from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.core.responses import success_response

from .models import Plan


class PublicPlanListView(APIView):
    """GET /api/v1/plans/ : active, public plans for pricing screens. Prices always come from the database."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def get(self, request):
        plans = Plan.objects.filter(is_active=True, is_public=True)
        data = [
            {
                "id": str(p.id), "name": p.name, "slug": p.slug, "description": p.description,
                "monthly_price": str(p.monthly_price), "currency": p.currency,
                "max_students": p.max_students, "max_teachers": p.max_teachers, "max_classes": p.max_classes,
                "features": p.features,
            }
            for p in plans
        ]
        return success_response(data, message="")
