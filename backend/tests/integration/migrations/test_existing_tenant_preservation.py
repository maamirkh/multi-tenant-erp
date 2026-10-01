"""[Gate A] Existing tenant data is untouched by migrations 057-061.

Covers tasks.md T030. Backward-compatibility guarantee (plan.md §33): the
only changes to existing tables are additive and nullable. Seeds
companies/roles/company_members/feature-flag rows at migration 056 (before
Epic 9A), upgrades to 061, and asserts every seeded row is byte-for-byte
identical — with the two new ``companies`` columns NULL.
"""

from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa

from .conftest import alembic_upgrade, db_engine


def _seed_pre_epic_9a_tenant(engine: sa.engine.Engine) -> dict[str, uuid.UUID]:
    user_id = uuid.uuid4()
    company_id = uuid.uuid4()
    role_id = uuid.uuid4()
    flag_id = uuid.uuid4()

    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO users (id, email, display_name) "
                "VALUES (:id, :email, :name)"
            ),
            {"id": user_id, "email": f"{user_id}@example.test", "name": "Pre-9A User"},
        )
        conn.execute(
            sa.text(
                "INSERT INTO companies (id, legal_name, slug, status, owner_id, "
                "email) VALUES (:id, :legal_name, :slug, 'active', :owner_id, "
                ":email)"
            ),
            {
                "id": company_id,
                "legal_name": "Pre-9A Test Co",
                "slug": f"pre-9a-co-{uuid.uuid4().hex[:8]}",
                "owner_id": user_id,
                "email": f"{company_id}@example.test",
            },
        )
        conn.execute(
            sa.text(
                "INSERT INTO roles (id, company_id, name, slug, rank) "
                "VALUES (:id, :company_id, 'Owner', 'owner', 100)"
            ),
            {"id": role_id, "company_id": company_id},
        )
        conn.execute(
            sa.text(
                "INSERT INTO company_members (id, company_id, user_id, role_id, "
                "status) VALUES (:id, :company_id, :user_id, :role_id, 'active')"
            ),
            {
                "id": uuid.uuid4(),
                "company_id": company_id,
                "user_id": user_id,
                "role_id": role_id,
            },
        )
        conn.execute(
            sa.text(
                "INSERT INTO inventory_feature_flags (id, company_id, flag_key, "
                "is_enabled) VALUES (:id, :company_id, "
                "'inventory.multi_warehouse', true)"
            ),
            {"id": flag_id, "company_id": company_id},
        )

    return {
        "user_id": user_id,
        "company_id": company_id,
        "role_id": role_id,
        "flag_id": flag_id,
    }


def _row_as_dict(
    engine: sa.engine.Engine, table: str, id_col: str, id_value
) -> dict[str, Any]:
    with engine.connect() as conn:
        row = (
            conn.execute(
                sa.text(f"SELECT * FROM {table} WHERE {id_col} = :id"),  # noqa: S608
                {"id": id_value},
            )
            .mappings()
            .one()
        )
    return dict(row)


class TestExistingTenantPreservation:
    def test_pre_epic_9a_rows_survive_057_to_061_unchanged(
        self, pg_test_db: str
    ) -> None:
        alembic_upgrade(pg_test_db, "056")
        engine = db_engine(pg_test_db)
        ids = _seed_pre_epic_9a_tenant(engine)

        company_before = _row_as_dict(engine, "companies", "id", ids["company_id"])
        role_before = _row_as_dict(engine, "roles", "id", ids["role_id"])
        member_before = _row_as_dict(
            engine, "company_members", "user_id", ids["user_id"]
        )
        flag_before = _row_as_dict(
            engine, "inventory_feature_flags", "id", ids["flag_id"]
        )

        alembic_upgrade(pg_test_db, "061")

        company_after = _row_as_dict(engine, "companies", "id", ids["company_id"])
        role_after = _row_as_dict(engine, "roles", "id", ids["role_id"])
        member_after = _row_as_dict(
            engine, "company_members", "user_id", ids["user_id"]
        )
        flag_after = _row_as_dict(
            engine, "inventory_feature_flags", "id", ids["flag_id"]
        )

        # New columns didn't exist at snapshot time — remove before compare,
        # then assert every pre-existing field is byte-for-byte identical.
        new_cols = {"pre_suspension_status", "access_invalidated_at"}
        company_after_comparable = {
            k: v for k, v in company_after.items() if k not in new_cols
        }
        assert company_after_comparable == company_before
        assert company_after["pre_suspension_status"] is None
        assert company_after["access_invalidated_at"] is None

        assert role_after == role_before
        assert member_after == member_before
        assert flag_after == flag_before

        engine.dispose()
