from rest_framework import serializers


class TenantScopedRelatedField(serializers.PrimaryKeyRelatedField):
    """The ONLY related-field type allowed on write serializers for tenant data: it can only see rows of the caller's
    school, so a payload can never point at another school's object (the error is the same 'does not exist')."""

    def get_queryset(self):
        queryset = super().get_queryset()
        request = self.context.get("request")
        school = getattr(getattr(request, "user", None), "school", None)
        if school is None:
            return queryset.none()
        return queryset.filter(school=school)
