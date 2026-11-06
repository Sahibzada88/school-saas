from django.db.models import Sum
from rest_framework.exceptions import ValidationError

from apps.core.images import normalize_image
from apps.platform_admin.config import PlatformConfig

from .models import ImageAsset


class ImageService:
    @staticmethod
    def store(school, data_url: str, kind: str = "photo") -> ImageAsset:
        """Validate (type, size, pixels, real decode) and store one image, enforcing the per-school storage quota."""
        image = normalize_image(data_url, kind)
        used = ImageAsset.objects.filter(school=school).aggregate(total=Sum("byte_size"))["total"] or 0
        quota = PlatformConfig.load().school_image_quota_mb * 1024 * 1024
        if used + image.size > quota:
            raise ValidationError("Your school's image storage quota is full. Remove unused photos or contact support.")
        return ImageAsset.objects.create(
            school=school, kind=kind, mime_type=image.mime_type, width=image.width, height=image.height,
            byte_size=image.size, sha256=image.sha256, data_base64=image.base64,
        )

    @staticmethod
    def replace(school, old: ImageAsset | None, value, kind: str = "photo") -> ImageAsset | None:
        """value: data URL to store, empty/None to clear. Deletes the previous asset so nothing orphans in the DB."""
        new = ImageService.store(school, value, kind) if value else None
        if old is not None:
            old.delete()
        return new


def image_url(asset_id) -> str | None:
    return f"/api/v1/school/images/{asset_id}/" if asset_id else None
