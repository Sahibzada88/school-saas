"""Strict validation of Base64 images before they are stored in PostgreSQL.

Why strict: every byte lives in the (free-tier, 500 MB) database. Limits: photos <= 150 KB / 512 px, logos <= 300 KB /
600 px, PNG/JPEG/WEBP only, verified by actually decoding with Pillow (the declared MIME type is never trusted), and
re-encoded so metadata/EXIF and any appended payload are stripped."""
import base64
import binascii
import hashlib
import io
import re
from dataclasses import dataclass

from rest_framework.exceptions import ValidationError

KIND_LIMITS = {"photo": (150 * 1024, 512), "logo": (300 * 1024, 600)}  # (max bytes, max width/height)
ALLOWED = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}
_DATA_URL = re.compile(r"^data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=\s]+)$")


@dataclass
class NormalizedImage:
    mime_type: str
    width: int
    height: int
    data: bytes
    sha256: str

    @property
    def size(self) -> int:
        return len(self.data)

    @property
    def base64(self) -> str:
        return base64.b64encode(self.data).decode("ascii")


def normalize_image(value: str, kind: str = "photo") -> NormalizedImage:
    from PIL import Image, UnidentifiedImageError

    max_bytes, max_dim = KIND_LIMITS[kind]
    match = _DATA_URL.match((value or "").strip())
    if not match:
        raise ValidationError("Upload a PNG, JPEG or WEBP image as a base64 data URL.")
    mime = match.group(1)
    # Reject oversize input before decoding anything (base64 inflates by ~4/3).
    if len(match.group(2)) > max_bytes * 4 // 3 + 16:
        raise ValidationError(f"Image is too large (max {max_bytes // 1024} KB).")
    try:
        raw = base64.b64decode(re.sub(r"\s+", "", match.group(2)), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValidationError("The image data is not valid base64.") from exc
    if len(raw) > max_bytes:
        raise ValidationError(f"Image is too large (max {max_bytes // 1024} KB).")

    try:
        with Image.open(io.BytesIO(raw)) as probe:
            probe.verify()
        image = Image.open(io.BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ValidationError("The file is not a valid image.") from exc
    if image.format != ALLOWED[mime]:
        raise ValidationError("The image content does not match its declared type.")
    width, height = image.size
    if width > max_dim or height > max_dim:
        raise ValidationError(f"Image is too large in pixels (max {max_dim}x{max_dim}).")

    out = io.BytesIO()
    if image.format == "JPEG":
        image.convert("RGB").save(out, format="JPEG", quality=85, optimize=True)
    else:
        image.save(out, format=image.format)  # re-encode: drops metadata and trailing bytes
    data = out.getvalue()
    if len(data) > max_bytes:
        raise ValidationError(f"Image is too large (max {max_bytes // 1024} KB).")
    return NormalizedImage(mime, width, height, data, hashlib.sha256(data).hexdigest())
