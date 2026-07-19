"""T136 — JWT claim completeness and correctness.

Verifies that every access token issued by JWTService contains all 9
required claims with correct types and values.
Spec ref: spec.md §13.2, NFR-008.
"""

from __future__ import annotations

import uuid

import jwt

_SETTINGS_KWARGS = {
    "DATABASE_URL": "sqlite:///:memory:",
    "SECRET_KEY": "test-secret-key-minimum-32-chars-ok",
    "JWT_SECRET_KEY": "test-jwt-secret-key-min-32-chars-ok!",
}

_REQUIRED_CLAIMS = ("sub", "iat", "exp", "nbf", "jti", "iss", "aud", "typ", "sid")


def _make_token() -> tuple[str, object]:
    """Create a fresh access token and return (raw_token, settings)."""
    from core.config.settings import Settings
    from modules.auth.services.jwt_service import JWTService

    settings = Settings(**_SETTINGS_KWARGS)
    svc = JWTService(settings)
    token = svc.create_access_token(
        user_id=uuid.uuid4(),
        email="claims_test@example.com",
        session_id=uuid.uuid4(),
    )
    return token, settings


class TestJWTClaims:
    def test_all_required_claims_present(self) -> None:
        """Access token must include all 9 required claims."""
        token, settings = _make_token()
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
        )
        for claim in _REQUIRED_CLAIMS:
            assert claim in payload, f"Required claim '{claim}' is missing from JWT"

    def test_token_lifetime_is_15_minutes(self) -> None:
        """exp - iat must equal 900 seconds (15 minutes)."""
        token, settings = _make_token()
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
        )
        lifetime = payload["exp"] - payload["iat"]
        assert lifetime == 900, f"Expected token lifetime 900s, got {lifetime}s"

    def test_typ_claim_is_access(self) -> None:
        """typ claim must be 'access' (not 'refresh' or any other type)."""
        token, settings = _make_token()
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
        )
        assert payload["typ"] == "access"

    def test_iss_matches_configured_issuer(self) -> None:
        """iss claim must match JWT_ISSUER from settings."""
        token, settings = _make_token()
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
        )
        assert payload["iss"] == settings.JWT_ISSUER

    def test_aud_matches_configured_audience(self) -> None:
        """aud claim must match JWT_AUDIENCE from settings."""
        token, settings = _make_token()
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
        )
        aud = payload["aud"]
        # PyJWT may decode aud as a list or string.
        if isinstance(aud, list):
            assert settings.JWT_AUDIENCE in aud
        else:
            assert aud == settings.JWT_AUDIENCE

    def test_sub_and_sid_are_valid_uuids(self) -> None:
        """sub and sid claims must be valid UUID strings."""
        token, settings = _make_token()
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
        )
        # Should not raise ValueError if valid UUIDs.
        uuid.UUID(payload["sub"])
        uuid.UUID(payload["sid"])

    def test_jti_is_unique_per_token(self) -> None:
        """Each token must have a unique jti (nonce)."""
        token1, settings = _make_token()
        token2, _ = _make_token()

        payload1 = jwt.decode(
            token1,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
        )
        payload2 = jwt.decode(
            token2,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
        )
        assert payload1["jti"] != payload2["jti"]

    def test_nbf_equals_iat(self) -> None:
        """nbf (not-before) must equal iat (issued-at) for immediate usability."""
        token, settings = _make_token()
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
        )
        assert payload["nbf"] == payload["iat"]
