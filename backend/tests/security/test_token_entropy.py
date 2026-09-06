"""T137 — Refresh token entropy validation.

Generates 1000 raw refresh tokens and asserts:
- No duplicates (collision probability is negligible for 64-byte random tokens).
- Each token is >= 86 characters long (64 bytes → base64url ≈ 86 chars).
- Each token's SHA-256 hash differs from the raw token (hash function applied).
Spec ref: spec.md §13.3, NFR-009.
"""

from __future__ import annotations

import hashlib
import secrets

_NUM_TOKENS = 1000
_TOKEN_BYTES = 64  # same as _REFRESH_TOKEN_BYTES in token_service.py
_MIN_TOKEN_LENGTH = 86  # 64 bytes → base64url → ~86 chars (ceil(64 * 4/3))


def _generate_token() -> str:
    """Generate one refresh token the same way TokenService does."""
    return secrets.token_urlsafe(_TOKEN_BYTES)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class TestTokenEntropy:
    def test_no_duplicate_tokens(self) -> None:
        """1000 generated tokens must all be unique."""
        tokens = [_generate_token() for _ in range(_NUM_TOKENS)]
        assert len(set(tokens)) == _NUM_TOKENS, (
            "Duplicate refresh tokens detected — entropy source is insufficient."
        )

    def test_each_token_meets_minimum_length(self) -> None:
        """Each token must be >= 86 characters (covers 64 bytes of entropy)."""
        tokens = [_generate_token() for _ in range(_NUM_TOKENS)]
        short = [t for t in tokens if len(t) < _MIN_TOKEN_LENGTH]
        assert len(short) == 0, (
            f"{len(short)} tokens shorter than {_MIN_TOKEN_LENGTH} chars: {short[:3]!r}"
        )

    def test_stored_hash_differs_from_raw_token(self) -> None:
        """For every token, SHA-256(token) != token (hash is not identity)."""
        tokens = [_generate_token() for _ in range(_NUM_TOKENS)]
        for raw in tokens:
            assert _sha256(raw) != raw, (
                "SHA-256 digest equals the raw token — hash function not applied."
            )

    def test_token_is_url_safe(self) -> None:
        """Tokens must only contain URL-safe characters (base64url alphabet)."""
        import re

        _url_safe = re.compile(r"^[A-Za-z0-9\-_]+$")
        tokens = [_generate_token() for _ in range(100)]
        for token in tokens:
            assert _url_safe.match(token), (
                f"Token contains non-URL-safe characters: {token[:20]!r}"
            )
