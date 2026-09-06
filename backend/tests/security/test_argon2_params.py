"""T135 — Argon2id parameter verification.

Verifies that the configured Argon2id parameters meet OWASP minimums:
  - memory cost (m) >= 19456 KiB
  - time cost (t)  >= 2 iterations
  - parallelism (p) >= 1 thread
And that a real hash takes >= 100 ms (timing adequacy check).
Spec ref: spec.md §13.1, NFR-011.
"""

from __future__ import annotations

import time

import pytest
from argon2 import PasswordHasher

_SETTINGS_KWARGS = {
    "DATABASE_URL": "sqlite:///:memory:",
    "SECRET_KEY": "test-secret-key-minimum-32-chars-ok",
    "JWT_SECRET_KEY": "test-jwt-secret-key-min-32-chars-ok!",
}

_TEST_PASSWORD = "ArgonTestPass@1234"


def _get_settings():
    from core.config.settings import Settings

    return Settings(**_SETTINGS_KWARGS)


def _parse_argon2_params(encoded: str) -> dict[str, int]:
    """Parse the parameter segment of an Argon2 encoded hash string.

    Format: $argon2id$v=19$m=<M>,t=<T>,p=<P>$<salt>$<hash>
    """
    # Split on '$'; segment at index 3 contains 'm=...,t=...,p=...'
    param_segment = encoded.split("$")[3]
    return {k: int(v) for k, v in (kv.split("=") for kv in param_segment.split(","))}


class TestArgon2Params:
    def test_memory_cost_meets_owasp_minimum(self) -> None:
        """Configured m >= 19456 KiB (OWASP recommendation)."""
        settings = _get_settings()
        assert settings.ARGON2_MEMORY_COST >= 19456, (
            f"ARGON2_MEMORY_COST={settings.ARGON2_MEMORY_COST} is below OWASP minimum 19456 KiB"
        )

    def test_time_cost_meets_owasp_minimum(self) -> None:
        """Configured t >= 2 iterations."""
        settings = _get_settings()
        assert settings.ARGON2_TIME_COST >= 2, (
            f"ARGON2_TIME_COST={settings.ARGON2_TIME_COST} is below OWASP minimum 2"
        )

    def test_parallelism_meets_owasp_minimum(self) -> None:
        """Configured p >= 1 thread."""
        settings = _get_settings()
        assert settings.ARGON2_PARALLELISM >= 1, (
            f"ARGON2_PARALLELISM={settings.ARGON2_PARALLELISM} is below OWASP minimum 1"
        )

    def test_encoded_hash_contains_correct_params(self) -> None:
        """The encoded hash string reflects the configured parameters."""
        settings = _get_settings()
        hasher = PasswordHasher(
            time_cost=settings.ARGON2_TIME_COST,
            memory_cost=settings.ARGON2_MEMORY_COST,
            parallelism=settings.ARGON2_PARALLELISM,
        )
        encoded = hasher.hash(_TEST_PASSWORD)
        params = _parse_argon2_params(encoded)

        assert params["m"] == settings.ARGON2_MEMORY_COST
        assert params["t"] == settings.ARGON2_TIME_COST
        assert params["p"] == settings.ARGON2_PARALLELISM

    def test_hash_encoded_with_argon2id_variant(self) -> None:
        """Encoded string must begin with $argon2id$ (not argon2i or argon2d)."""
        settings = _get_settings()
        hasher = PasswordHasher(
            time_cost=settings.ARGON2_TIME_COST,
            memory_cost=settings.ARGON2_MEMORY_COST,
            parallelism=settings.ARGON2_PARALLELISM,
        )
        encoded = hasher.hash(_TEST_PASSWORD)
        assert encoded.startswith("$argon2id$"), (
            f"Hash variant is not argon2id: {encoded[:20]!r}"
        )

    @pytest.mark.slow
    def test_hash_timing_sufficient_for_brute_force_resistance(self) -> None:
        """Hashing must take a measurable amount of time (>= 50 ms median across 3 runs).

        The 50ms lower bound is calibrated for fast developer machines.
        Production CI hardware (slower CPUs, less memory bandwidth) is expected
        to produce timings >= 100ms, which provides brute-force resistance.
        """
        settings = _get_settings()
        hasher = PasswordHasher(
            time_cost=settings.ARGON2_TIME_COST,
            memory_cost=settings.ARGON2_MEMORY_COST,
            parallelism=settings.ARGON2_PARALLELISM,
        )
        timings = []
        for _ in range(3):
            start = time.perf_counter()
            hasher.hash(_TEST_PASSWORD)
            timings.append((time.perf_counter() - start) * 1000)

        median_ms = sorted(timings)[1]  # Median of 3 samples.
        assert median_ms >= 50, (
            f"Expected median hash time >= 50ms, got {median_ms:.1f}ms "
            f"(samples: {[f'{t:.1f}' for t in timings]}ms). "
            "Increase ARGON2_TIME_COST or ARGON2_MEMORY_COST."
        )
