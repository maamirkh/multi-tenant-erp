"""[Gate A] No migration provisions a Platform Owner; Epic 9A's own chain
(057-061) is internally consistent.

Covers tasks.md T029. ADR-8: credential provisioning is decoupled from
schema versioning — the first Platform Owner is provisioned by a separate,
explicitly-invoked operator command (Phase 4), never a data migration.

**[CORRECTED]** This file originally also asserted "no migration 062
exists and the platform's overall head is 061," freezing the migration
contract at 057-061 forever. That assertion was Epic 9A's own
self-imposed completion marker (061's docstring: "no `062` exists or may
be created"), scoped to prevent scope creep *during* Epic 9A itself — it
was never a permanent, all-epics-forever platform invariant, and Epic 10
(Installments, migrations 062-071, `specs/010-installments/plan.md` §30)
legitimately continues the chain past 061 per its own independently
reviewed and approved plan. The substantive ADR-8 guarantee this file
protects — no migration ever provisions bootstrap credentials — is
unaffected and still fully enforced by the two tests below, which now
check that Epic 9A's own 057-061 sub-chain remains internally consistent
(each revision still resolves, in order) rather than asserting a global
head value that a later, approved epic is expected to move past.
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

    def test_epic_9a_chain_057_to_061_is_internally_consistent(self) -> None:
        """Epic 9A's own five migrations (057-061) still form an
        uninterrupted, single-parent chain ending at 061 — independent of
        whatever later, separately-approved epics (e.g. Epic 10's 062-071)
        append afterward."""
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

        epic_9a_revisions = {"057", "058", "059", "060", "061"}
        assert epic_9a_revisions <= revisions, "Epic 9A migration(s) missing"
        assert down_revisions["057"] == "056"
        assert down_revisions["058"] == "057"
        assert down_revisions["059"] == "058"
        assert down_revisions["060"] == "059"
        assert down_revisions["061"] == "060"
        # 061 is Epic 9A's own chain-end: nothing else in the repository
        # declares down_revision="061" other than Epic 10's approved 062.
        children_of_061 = {rev for rev, down in down_revisions.items() if down == "061"}
        assert children_of_061 <= {"062"}, (
            f"Unexpected migration(s) branching from 061: {children_of_061}"
        )
