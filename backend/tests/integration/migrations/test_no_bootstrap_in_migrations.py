"""[Gate A] No migration provisions a Platform Owner; no migration 062 exists.

Covers tasks.md T029. ADR-8: credential provisioning is decoupled from
schema versioning — the first Platform Owner is provisioned by a separate,
explicitly-invoked operator command (Phase 4), never a data migration.
This also freezes the migration contract at 057-061.
"""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa

from .conftest import alembic_upgrade, db_engine

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations" / "versions"

_BOOTSTRAP_ENV_VARS = (
    "PLATFORM_OWNER_BOOTSTRAP_EMAIL",
    "PLATFORM_OWNER_BOOTSTRAP_PASSWORD_HASH",
)


class TestNoBootstrapInMigrations:
    def test_platform_administrators_empty_after_upgrade_head(
        self, pg_test_db: str
    ) -> None:
        alembic_upgrade(pg_test_db, "head")
        engine = db_engine(pg_test_db)
        with engine.connect() as conn:
            count = conn.execute(
                sa.text("SELECT count(*) FROM platform_administrators")
            ).scalar()
        assert count == 0
        engine.dispose()

    def test_no_migration_file_references_bootstrap_env_vars(self) -> None:
        offenders: list[str] = []
        for path in sorted(MIGRATIONS_DIR.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            for var in _BOOTSTRAP_ENV_VARS:
                if var in text:
                    offenders.append(f"{path.name}: references {var}")
        assert offenders == [], (
            "Bootstrap credential provisioning must never be a migration "
            f"(ADR-8): {offenders}"
        )

    def test_no_migration_062_exists_and_head_is_061(self) -> None:
        offenders = [path.name for path in MIGRATIONS_DIR.glob("062_*.py")]
        assert offenders == [], f"Forbidden migration 062 found: {offenders}"

        revisions = set()
        down_revisions: dict[str, str | None] = {}
        for path in sorted(MIGRATIONS_DIR.glob("0*.py")):
            text = path.read_text(encoding="utf-8")
            rev_match = None
            down_match = None
            for line in text.splitlines():
                stripped = line.strip()
                if (
                    stripped.startswith("revision")
                    and "=" in stripped
                    and rev_match is None
                ):
                    rev_match = stripped.split("=", 1)[1].strip().strip('"').strip("'")
                if (
                    stripped.startswith("down_revision")
                    and "=" in stripped
                    and down_match is None
                ):
                    raw = stripped.split("=", 1)[1].strip()
                    down_match = (
                        None if raw.startswith("None") else raw.strip('"').strip("'")
                    )
            if rev_match:
                revisions.add(rev_match)
                down_revisions[rev_match] = down_match

        heads = revisions - {d for d in down_revisions.values() if d}
        assert heads == {"061"}, f"Expected head '061', found heads: {heads}"
