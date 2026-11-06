import base64

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from apps.core.images import normalize_image
from apps.core.testing import png_data_url


class ImageValidationTests(SimpleTestCase):
    def test_valid_images_are_accepted_and_reencoded(self):
        for fmt in ("PNG", "JPEG", "WEBP"):
            image = normalize_image(png_data_url(fmt=fmt), "photo")
            self.assertEqual((image.width, image.height), (10, 10))
            self.assertTrue(image.mime_type.endswith(fmt.lower()))
            self.assertEqual(len(image.sha256), 64)

    def test_rejects_non_image_data_urls(self):
        for bad in ("", "hello", "data:text/html;base64,PGgxPmhpPC9oMT4=", "data:image/svg+xml;base64,PHN2Zy8+", "data:image/png;base64,@@@@"):
            with self.assertRaises(ValidationError, msg=bad):
                normalize_image(bad)

    def test_rejects_content_that_is_not_really_an_image(self):
        fake = "data:image/png;base64," + base64.b64encode(b"<script>alert(1)</script>").decode()
        with self.assertRaises(ValidationError):
            normalize_image(fake)

    def test_rejects_declared_type_that_does_not_match_content(self):
        jpeg_as_png = png_data_url(fmt="JPEG").replace("image/jpeg", "image/png")
        with self.assertRaises(ValidationError):
            normalize_image(jpeg_as_png)

    def test_dimension_limits_depend_on_the_kind(self):
        big = png_data_url(size=(580, 580))
        with self.assertRaises(ValidationError):
            normalize_image(big, "photo")  # > 512 px
        self.assertEqual(normalize_image(big, "logo").width, 580)  # logos may be 600 px

    def test_byte_size_limit(self):
        import io
        import os

        from PIL import Image

        noisy = Image.frombytes("RGB", (300, 300), os.urandom(300 * 300 * 3))  # incompressible
        buffer = io.BytesIO()
        noisy.save(buffer, format="PNG")
        with self.assertRaises(ValidationError):
            normalize_image("data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode(), "photo")
