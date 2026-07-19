"""Unit tests for JWTService.

Covers: token creation, validation, claim extraction, expiry, and tamper detection.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import jwt
import pytest

from core.auth.exceptions import AuthenticationException, TokenExpiredException
from core.config.settings import Settings
from core.utils.datetime import utcnow
from modules.auth.services.jwt_service import JWTService

_SETTINGS = Settings(
    DATABASE_URL="postgresql://x:x@localhost/x",
    SECRET_KEY="test-secret-key-minimum-32-chars-ok",
    JWT_SECRET_KEY="test-jwt-secret-key-min-32-chars-ok!",
    JWT_ALGORITHM="HS256",
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15,
    JWT_ISSUER="devsphere-erp",
    JWT_AUDIENCE="devsphere-erp-api",
    JWT_CLOCK_SKEW_SECONDS=0,
)


@pytest.fixture
def svc() -> JWTService:
    return JWTService(_SETTINGS)


@pytest.fixture
def valid_token(svc: JWTService) -> str:
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    return svc.create_access_token(
        user_id=user_id, email="user@example.com", session_id=session_id
    )


class TestCreateAccessToken:
    def test_returns_string(self, svc: JWTService) -> None:
        token = svc.create_access_token(uuid.uuid4(), "u@e.com", uuid.uuid4())
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_has_three_parts(self, svc: JWTService) -> None:
        token = svc.create_access_token(uuid.uuid4(), "u@e.com", uuid.uuid4())
        assert len(token.split(".")) == 3

    def test_claims_contain_required_fields(self, svc: JWTService) -> None:
        user_id = uuid.uuid4()
        session_id = uuid.uuid4()
        token = svc.create_access_token(user_id, "u@e.com", session_id)
        claims = jwt.decode(
            token,
            _SETTINGS.JWT_SECRET_KEY,
            algorithms=[_SETTINGS.JWT_ALGORITHM],
            audience=_SETTINGS.JWT_AUDIENCE,
        )
        assert claims["sub"] == str(user_id)
        assert claims["sid"] == str(session_id)
        assert claims["email"] == "u@e.com"
        assert claims["typ"] == "access"
        assert "jti" in claims
        assert "iss" in claims
        assert "aud" in claims
        assert "exp" in claims
        assert "iat" in claims
        assert "nbf" in claims


class TestDecodeAccessToken:
    def test_valid_token_returns_claims(
        self, svc: JWTService, valid_token: str
    ) -> None:
        claims = svc.decode_access_token(valid_token)
        assert "sub" in claims
        assert "sid" in claims

    def test_expired_token_raises_token_expired(self, svc: JWTService) -> None:
        # Create a token that expired 10 seconds ago.
        now = utcnow()
        payload = {
            "sub": str(uuid.uuid4()),
            "sid": str(uuid.uuid4()),
            "email": "u@e.com",
            "iat": now - timedelta(minutes=20),
            "exp": now - timedelta(minutes=5),
            "nbf": now - timedelta(minutes=20),
            "jti": str(uuid.uuid4()),
            "iss": _SETTINGS.JWT_ISSUER,
            "aud": _SETTINGS.JWT_AUDIENCE,
            "typ": "access",
        }
        expired_token = jwt.encode(
            payload, _SETTINGS.JWT_SECRET_KEY, algorithm=_SETTINGS.JWT_ALGORITHM
        )
        with pytest.raises(TokenExpiredException):
            svc.decode_access_token(expired_token)

    def test_tampered_signature_raises_auth_exception(
        self, svc: JWTService, valid_token: str
    ) -> None:
        # Flip the last character of the signature to tamper it.
        parts = valid_token.split(".")
        tampered = parts[2][:-1] + ("A" if parts[2][-1] != "A" else "B")
        bad_token = ".".join(parts[:2] + [tampered])
        with pytest.raises(AuthenticationException):
            svc.decode_access_token(bad_token)

    def test_wrong_issuer_raises_auth_exception(self) -> None:
        bad_settings = Settings(
            DATABASE_URL="postgresql://x:x@localhost/x",
            SECRET_KEY="test-secret-key-minimum-32-chars-ok",
            JWT_SECRET_KEY="test-jwt-secret-key-min-32-chars-ok!",
            JWT_ISSUER="wrong-issuer",
            JWT_AUDIENCE="devsphere-erp-api",
            JWT_CLOCK_SKEW_SECONDS=0,
        )
        bad_svc = JWTService(bad_settings)
        token = bad_svc.create_access_token(uuid.uuid4(), "u@e.com", uuid.uuid4())
        # Now try to decode with correct-issuer settings.
        good_svc = JWTService(_SETTINGS)
        with pytest.raises(AuthenticationException):
            good_svc.decode_access_token(token)

    def test_garbage_string_raises_auth_exception(self, svc: JWTService) -> None:
        with pytest.raises(AuthenticationException):
            svc.decode_access_token("not.a.jwt")

    def test_alg_none_attack_raises_auth_exception(
        self, svc: JWTService, valid_token: str
    ) -> None:
        # Construct a token with alg=none by manually building the header.
        import base64

        header = (
            base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}')
            .rstrip(b"=")
            .decode()
        )
        parts = valid_token.split(".")
        none_token = f"{header}.{parts[1]}."
        with pytest.raises(AuthenticationException):
            svc.decode_access_token(none_token)


class TestExtractClaims:
    def test_extract_user_id(self, svc: JWTService) -> None:
        user_id = uuid.uuid4()
        token = svc.create_access_token(user_id, "u@e.com", uuid.uuid4())
        claims = svc.decode_access_token(token)
        extracted = svc.extract_user_id(claims)
        assert extracted == user_id

    def test_extract_session_id(self, svc: JWTService) -> None:
        session_id = uuid.uuid4()
        token = svc.create_access_token(uuid.uuid4(), "u@e.com", session_id)
        claims = svc.decode_access_token(token)
        extracted = svc.extract_session_id(claims)
        assert extracted == session_id

    def test_missing_sub_raises(self, svc: JWTService) -> None:
        with pytest.raises(AuthenticationException):
            svc.extract_user_id({})

    def test_missing_sid_raises(self, svc: JWTService) -> None:
        with pytest.raises(AuthenticationException):
            svc.extract_session_id({})
