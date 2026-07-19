"""T128A — Invalid JWT rejection tests.

Verifies that malformed, tampered, and algorithmically-invalid JWTs are
rejected with 401 — not 500 — on GET /auth/me.
Spec ref: spec.md §8 NFR-009, plan.md §7 (JWTService).
"""

from __future__ import annotations

import base64
import uuid
from datetime import timedelta

import jwt
from fastapi.testclient import TestClient

_VALID_KEY = "test-jwt-secret-key-min-32-chars-ok!"
_VALID_ALG = "HS256"
_ISSUER = "devsphere-erp"
_AUDIENCE = "devsphere-erp-api"


def _encode(payload: dict, key: str = _VALID_KEY, alg: str = _VALID_ALG) -> str:
    return jwt.encode(payload, key, algorithm=alg)


def _me(client: TestClient, token: str) -> int:
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    return resp.status_code


def _base_payload() -> dict:
    from core.utils.datetime import utcnow

    now = utcnow()
    return {
        "sub": str(uuid.uuid4()),
        "sid": str(uuid.uuid4()),
        "email": "test@example.com",
        "typ": "access",
        "jti": str(uuid.uuid4()),
        "iss": _ISSUER,
        "aud": _AUDIENCE,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=15),
    }


class TestMalformedJWT:
    def test_garbage_string_rejected(self, test_client: TestClient) -> None:
        assert _me(test_client, "not-a-jwt") == 401

    def test_two_parts_only_rejected(self, test_client: TestClient) -> None:
        assert _me(test_client, "header.payload") == 401

    def test_empty_string_rejected(self, test_client: TestClient) -> None:
        assert _me(test_client, "") == 401 or _me(test_client, "") == 403


class TestTamperedJWT:
    def test_tampered_signature_rejected(self, test_client: TestClient) -> None:
        payload = _base_payload()
        token = _encode(payload)
        parts = token.split(".")
        tampered = parts[2][:-1] + ("A" if parts[2][-1] != "A" else "B")
        assert _me(test_client, ".".join(parts[:2] + [tampered])) == 401

    def test_wrong_key_rejected(self, test_client: TestClient) -> None:
        payload = _base_payload()
        token = _encode(payload, key="totally-different-secret-key-9999!")
        assert _me(test_client, token) == 401


class TestAlgorithmAttacks:
    def test_alg_none_rejected(self, test_client: TestClient) -> None:
        payload = _base_payload()
        # Craft a token with alg=none header manually.
        header = (
            base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}')
            .rstrip(b"=")
            .decode()
        )
        valid_token = _encode(payload)
        payload_part = valid_token.split(".")[1]
        none_token = f"{header}.{payload_part}."
        assert _me(test_client, none_token) == 401


class TestClaimValidation:
    def test_expired_token_rejected(self, test_client: TestClient) -> None:
        from core.utils.datetime import utcnow

        now = utcnow()
        payload = _base_payload()
        payload["exp"] = now - timedelta(minutes=5)
        payload["nbf"] = now - timedelta(minutes=20)
        token = _encode(payload)
        assert _me(test_client, token) == 401

    def test_wrong_issuer_rejected(self, test_client: TestClient) -> None:
        payload = _base_payload()
        payload["iss"] = "evil-issuer"
        token = _encode(payload)
        assert _me(test_client, token) == 401

    def test_wrong_audience_rejected(self, test_client: TestClient) -> None:
        payload = _base_payload()
        payload["aud"] = "wrong-audience"
        token = _encode(payload)
        assert _me(test_client, token) == 401

    def test_missing_sid_rejected(self, test_client: TestClient) -> None:
        payload = _base_payload()
        del payload["sid"]
        token = _encode(payload)
        assert _me(test_client, token) == 401
