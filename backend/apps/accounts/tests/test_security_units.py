from datetime import timedelta

from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.accounts.services.tokens import TokenError, decode_token, encode_token
from apps.core.csrf import csrf_tokens_match, generate_csrf_token, is_valid_csrf_token
from apps.core.utils import get_client_ip

SECRET = "s" * 40


class CsrfTokenTests(SimpleTestCase):
    def test_generated_token_is_valid_and_unique(self):
        a, b = generate_csrf_token(), generate_csrf_token()
        self.assertNotEqual(a, b)
        self.assertTrue(is_valid_csrf_token(a))

    def test_forged_or_malformed_tokens_are_rejected(self):
        self.assertFalse(is_valid_csrf_token("abc.def"))
        self.assertFalse(is_valid_csrf_token("nodot"))
        self.assertFalse(is_valid_csrf_token(""))
        self.assertFalse(is_valid_csrf_token(None))

    def test_cookie_and_header_must_match(self):
        token = generate_csrf_token()
        self.assertTrue(csrf_tokens_match(token, token))
        self.assertFalse(csrf_tokens_match(token, generate_csrf_token()))
        self.assertFalse(csrf_tokens_match(token, None))
        self.assertFalse(csrf_tokens_match("x.y", "x.y"))  # equal but not signed


class ClientIPTests(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()

    @override_settings(PROXY_SHARED_SECRET=SECRET, TRUSTED_IP_HEADER="")
    def test_forwarded_ip_is_trusted_only_with_the_shared_secret(self):
        ok = self.rf.get("/", HTTP_X_PROXY_SECRET=SECRET, HTTP_X_CLIENT_IP="203.0.113.5", REMOTE_ADDR="10.0.0.1")
        self.assertEqual(get_client_ip(ok), "203.0.113.5")
        wrong = self.rf.get("/", HTTP_X_PROXY_SECRET="nope", HTTP_X_CLIENT_IP="203.0.113.5", REMOTE_ADDR="10.0.0.1")
        self.assertEqual(get_client_ip(wrong), "10.0.0.1")
        missing = self.rf.get("/", HTTP_X_CLIENT_IP="203.0.113.5", REMOTE_ADDR="10.0.0.1")
        self.assertEqual(get_client_ip(missing), "10.0.0.1")

    @override_settings(PROXY_SHARED_SECRET="", TRUSTED_IP_HEADER="")
    def test_spoofed_headers_are_ignored_when_no_secret_is_configured(self):
        request = self.rf.get("/", HTTP_X_PROXY_SECRET="", HTTP_X_CLIENT_IP="203.0.113.5", HTTP_X_FORWARDED_FOR="1.2.3.4", REMOTE_ADDR="10.0.0.1")
        self.assertEqual(get_client_ip(request), "10.0.0.1")

    @override_settings(PROXY_SHARED_SECRET=SECRET, TRUSTED_IP_HEADER="")
    def test_garbage_forwarded_ip_falls_back(self):
        request = self.rf.get("/", HTTP_X_PROXY_SECRET=SECRET, HTTP_X_CLIENT_IP="not-an-ip", REMOTE_ADDR="10.0.0.1")
        self.assertEqual(get_client_ip(request), "10.0.0.1")

    @override_settings(PROXY_SHARED_SECRET="", TRUSTED_IP_HEADER="HTTP_X_FORWARDED_FOR")
    def test_configured_trusted_header_is_used(self):
        request = self.rf.get("/", HTTP_X_FORWARDED_FOR="198.51.100.7, 10.0.0.2", REMOTE_ADDR="10.0.0.1")
        self.assertEqual(get_client_ip(request), "198.51.100.7")


@override_settings(SECRET_KEY="k" * 50, JWT_SIGNING_KEY="")
class TokenTests(SimpleTestCase):
    def test_round_trip(self):
        token = encode_token(typ="access", sub="abc", lifetime=timedelta(minutes=5), sid="s1")
        payload = decode_token(token, "access")
        self.assertEqual(payload["sub"], "abc")
        self.assertEqual(payload["sid"], "s1")

    def test_wrong_type_is_rejected(self):
        token = encode_token(typ="refresh", sub="abc", lifetime=timedelta(minutes=5))
        with self.assertRaises(TokenError) as ctx:
            decode_token(token, "access")
        self.assertEqual(ctx.exception.reason, "invalid")

    def test_expired_token_is_reported_as_expired(self):
        token = encode_token(typ="access", sub="abc", lifetime=timedelta(minutes=-5))
        with self.assertRaises(TokenError) as ctx:
            decode_token(token, "access")
        self.assertEqual(ctx.exception.reason, "expired")

    def test_tampered_token_is_rejected(self):
        token = encode_token(typ="access", sub="abc", lifetime=timedelta(minutes=5))
        with self.assertRaises(TokenError):
            decode_token(token[:-3] + ("AAA" if not token.endswith("AAA") else "BBB"), "access")

    def test_token_signed_with_another_key_is_rejected(self):
        token = encode_token(typ="access", sub="abc", lifetime=timedelta(minutes=5))
        with override_settings(SECRET_KEY="z" * 50):
            with self.assertRaises(TokenError):
                decode_token(token, "access")
