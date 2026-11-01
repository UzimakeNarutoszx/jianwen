import base64
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.core.security import create_access_token, hash_password, verify_access_token, verify_password


def _decode_payload(token: str) -> dict:
    payload_token = token.split(".", 1)[0]
    payload_token += "=" * (-len(payload_token) % 4)
    return json.loads(base64.urlsafe_b64decode(payload_token).decode("utf-8"))


def _encode_payload(payload: dict) -> str:
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")


class SecurityTests(unittest.TestCase):
    def test_password_hash_verifies_only_original_password(self) -> None:
        password_hash = hash_password("correct-password")

        self.assertTrue(verify_password("correct-password", password_hash))
        self.assertFalse(verify_password("wrong-password", password_hash))
        self.assertFalse(verify_password("correct-password", "not-a-valid-hash"))

    def test_access_token_round_trip_and_tamper_rejection(self) -> None:
        token = create_access_token(42)

        self.assertEqual(verify_access_token(token), 42)

        payload = _decode_payload(token)
        payload["sub"] = "43"
        tampered_token = f"{_encode_payload(payload)}.{token.split('.', 1)[1]}"

        self.assertIsNone(verify_access_token(tampered_token))

    def test_expired_access_token_is_rejected(self) -> None:
        with patch("app.core.security.settings", SimpleNamespace(ACCESS_TOKEN_EXPIRE_SECONDS=60, SECRET_KEY="test-key")):
            with patch("app.core.security.time.time", return_value=100):
                token = create_access_token(42)
            with patch("app.core.security.time.time", return_value=159):
                self.assertEqual(verify_access_token(token), 42)
            for now in (160, 161):
                with patch("app.core.security.time.time", return_value=now):
                    self.assertIsNone(verify_access_token(token))

    def test_non_ascii_or_malformed_token_is_rejected_without_exception(self) -> None:
        for token in ("abc.中文", "é.abc", "", "missing-separator", "a.b.c"):
            self.assertIsNone(verify_access_token(token))


if __name__ == "__main__":
    unittest.main()
