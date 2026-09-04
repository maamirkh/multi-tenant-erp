"""[Epic 10, Phase 14, T242] Confirm no test in the entire Installments
suite relies on SQLite-only behavior for locking/partial-index
assertions. A grep sweep of ``tests/integration/repositories/
installments/`` and ``tests/integration/api/v1/installments/`` for
real-Postgres fixture usage on every concurrency-relevant test —
row-level locking (``FOR UPDATE``), optimistic version-check races,
partial unique indexes, and ``INSERT ... ON CONFLICT`` idempotency
semantics are all PostgreSQL-specific and unprovable against SQLite's
in-memory engine (plan.md §31/§32's explicit "SQLite is NOT final proof
of PostgreSQL-specific behavior").

This is a durable, automated version of the audit rather than a one-off
manual check — re-run on every backend test invocation, it fails the
moment a future contribution adds a concurrency-relevant test file
without wiring it to the real-Postgres fixture chain
(``pg_test_db``/``db_engine``/``pg_engine``,
``tests.integration.migrations.conftest``'s established convention).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


def _find_backend_root() -> Path:
    # This file lives at <backend_root>/tests/integration/repositories/
    # installments/<this file> — four parents up is always the backend
    # root regardless of what the containing checkout/mount is named
    # (e.g. the erp-api-verify container mounts it at /app, not a
    # directory literally named "backend" — name-matching would break
    # there even though the relative structure is identical).
    here = Path(__file__).resolve()
    candidate = here.parents[4]
    assert (candidate / "modules" / "installments").is_dir(), (
        f"expected {candidate} to be the backend root (containing "
        f"modules/installments/), got a directory structure that doesn't match"
    )
    return candidate


_BACKEND_ROOT = _find_backend_root()
_TARGET_DIRS = [
    _BACKEND_ROOT / "tests" / "integration" / "repositories" / "installments",
    _BACKEND_ROOT / "tests" / "integration" / "api" / "v1" / "installments",
]

# Filename signal for "this test is concurrency/locking/partial-index
# relevant" — matches every file this sweep actually found at authoring
# time (test_concurrency_*.py, test_*_race.py, test_concurrent_*.py,
# test_contract_one_per_obligation.py, test_idempotency_*.py,
# test_settlement_concurrency.py, test_writeoff_collection_race.py) —
# broad enough to also catch any future file following the same naming
# convention, not hand-maintained as a fixed list.
_CONCURRENCY_RELEVANT_NAME = re.compile(
    r"concurren|_race\.py$|obligation|idempot|unique", re.IGNORECASE
)

# Any of these markers proves the file is wired to the real-Postgres
# fixture chain (either it imports the shared migrations-conftest
# fixtures directly, or it consumes the api/v1/installments/conftest.py
# `pg_engine` fixture already built on that same chain, or it defines
# its own local `pg_engine`/`db_session` pair shadowing them — this
# file's own sibling T236-T241 files all do exactly one of these).
_REAL_POSTGRES_MARKERS = (
    "pg_test_db",
    "pg_engine",
    "tests.integration.migrations.conftest",
)

_SQLITE_MARKER = re.compile(r"sqlite", re.IGNORECASE)


def _concurrency_relevant_files() -> list[Path]:
    files: list[Path] = []
    for directory in _TARGET_DIRS:
        assert directory.is_dir(), f"expected directory to exist: {directory}"
        for path in sorted(directory.glob("test_*.py")):
            if _CONCURRENCY_RELEVANT_NAME.search(path.name):
                files.append(path)
    return files


class TestNoSqliteRelianceForConcurrencyAssertions:
    def test_target_directories_exist_and_are_scanned(self) -> None:
        # A regression-proof for the sweep itself: if either directory
        # ever moved, this must fail loudly rather than silently
        # scanning zero files and reporting a false "all clear".
        for directory in _TARGET_DIRS:
            assert directory.is_dir(), f"missing target directory: {directory}"

    def test_sweep_finds_the_known_concurrency_relevant_files(self) -> None:
        found_names = {p.name for p in _concurrency_relevant_files()}
        # The complete set discovered when this sweep was authored
        # (Phase 14) — every prior phase's dedicated race/idempotency/
        # partial-unique-index test, plus this phase's own T236-T241.
        # Asserting the set is a SUPERSET (not equality) lets future
        # phases add more without needing to edit this list, while
        # still catching an accidental rename/deletion of an existing
        # one going undetected.
        expected_minimum = {
            "test_concurrency_hardening.py",
            "test_concurrency_collections_scale.py",
            "test_concurrency_collection_vs_late_charge_scale.py",
            "test_concurrency_collection_vs_settlement_scale.py",
            "test_concurrency_lifecycle_transitions_scale.py",
            "test_concurrency_idempotency_scale.py",
            # Exit Gate gap-closures: plan.md §19 races named but not
            # covered by any earlier phase nor by T236-T241's literal
            # enumeration (see each file's own module docstring).
            "test_concurrency_activation_race.py",
            "test_concurrency_collection_vs_reversal_race.py",
            "test_contract_one_per_obligation.py",
            "test_idempotency_concurrency.py",
            "test_idempotency_scoping.py",
            "test_idempotency_replay_conflict.py",
            "test_approve_reject_race.py",
            "test_concurrent_collections.py",
            "test_concurrent_collection_vs_late_charge.py",
            "test_settlement_concurrency.py",
            "test_writeoff_collection_race.py",
        }
        missing = expected_minimum - found_names
        assert not missing, (
            f"expected concurrency-relevant test files not found by the naming-"
            f"pattern sweep (renamed/deleted without updating this list?): {missing}"
        )

    @pytest.mark.parametrize(
        "path",
        _concurrency_relevant_files(),
        ids=lambda p: p.name,
    )
    def test_file_is_wired_to_real_postgres_not_sqlite_only(self, path: Path) -> None:
        source = path.read_text(encoding="utf-8")

        uses_real_postgres_fixture = any(
            marker in source for marker in _REAL_POSTGRES_MARKERS
        )
        # A file under api/v1/installments/ that merely takes
        # `db_session` as a fixture parameter (no explicit marker of its
        # own in source) is STILL provably real-Postgres: that
        # directory's own conftest.py binds `db_session` to a real
        # `pg_engine` (verified by direct inspection — it is not the
        # repo-root's different, SQLite-capable `db_session` of the same
        # name, since pytest fixture resolution always prefers the
        # closest conftest.py in the directory chain). Files under
        # repositories/installments/ get NO such automatic guarantee —
        # that directory has no local conftest.py, which is exactly the
        # gap T237-T241 each had to close by defining their own local
        # pg_engine/db_session pair (this file's own module docstring
        # sibling files) — so a bare `db_session` reference there is
        # NOT accepted as sufficient proof.
        if not uses_real_postgres_fixture and "api/v1/installments" in str(
            path.as_posix()
        ):
            uses_real_postgres_fixture = "db_session" in source

        assert uses_real_postgres_fixture, (
            f"{path.name} matches the concurrency/locking/partial-index naming "
            f"pattern but references none of {_REAL_POSTGRES_MARKERS} (nor, for "
            f"an api/v1/installments/ file, its directory-guaranteed real-Postgres "
            f"`db_session`) — it cannot be proving PostgreSQL-specific locking/"
            f"index behavior without the real-Postgres fixture chain (plan.md "
            f"§31/§32)."
        )

        # A concurrency-relevant file may legitimately mention "sqlite"
        # only in prose explaining why it does NOT rely on it (several
        # of this sweep's own sibling files do exactly that in their
        # module docstrings) — so this is a soft signal surfaced for
        # human review via the assertion message, not a hard failure by
        # itself; the hard requirement already proven above is that a
        # real-Postgres fixture is actually wired in. If a file ever
        # constructs its own competing in-memory/SQLite engine instead
        # of using the shared real-Postgres chain for its actual
        # locking/index assertions, that would show up as constructing
        # an `Engine`/`create_engine` bound to a sqlite:// URL alongside
        # the sqlite mention — checked explicitly here.
        sqlite_engine_construction = re.search(
            r"create_engine\(\s*[\"']sqlite", source, re.IGNORECASE
        )
        assert sqlite_engine_construction is None, (
            f"{path.name} constructs a SQLite engine directly — a concurrency/"
            f"locking/partial-index test must use the real-Postgres fixture "
            f"chain exclusively, never fall back to an in-memory SQLite engine "
            f"for the assertions under test."
        )
