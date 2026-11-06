from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.responses import Envelope
from apps.core.testing import api_client


class HealthEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_health_returns_envelope(self):
        response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["status"], "ok")
        self.assertIn("message", body)

    def test_health_with_db_check(self):
        response = self.client.get("/api/v1/health/?db=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["database"], "ok")

    def test_request_id_header_is_set_and_echoed_when_valid(self):
        response = self.client.get("/api/v1/health/", HTTP_X_REQUEST_ID="abc12345-valid")
        self.assertEqual(response["X-Request-ID"], "abc12345-valid")

    def test_malformed_request_id_is_replaced(self):
        response = self.client.get("/api/v1/health/", HTTP_X_REQUEST_ID="bad id with spaces!!")
        self.assertRegex(response["X-Request-ID"], r"^[0-9a-f]{32}$")

    def test_api_responses_are_not_cacheable(self):
        response = self.client.get("/api/v1/health/")
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_unknown_route_returns_json_envelope_404(self):
        response = self.client.get("/api/v1/does-not-exist/")
        self.assertEqual(response.status_code, 404)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["code"], "not_found")
        self.assertIn("request_id", body)

    def test_method_not_allowed_uses_error_envelope(self):
        response = api_client().post("/api/v1/health/", {})  # CSRF-valid client, so the 405 is reachable
        self.assertEqual(response.status_code, 405)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertNotIn("Traceback", str(body))


class EnvelopeTests(TestCase):
    def test_envelope_is_a_dict_marker(self):
        env = Envelope(success=True, data=1, message="")
        self.assertIsInstance(env, dict)
        self.assertEqual(env["data"], 1)
