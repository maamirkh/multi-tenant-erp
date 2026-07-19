"""Seed script — insert 10,000 company records into the target PostgreSQL database.

Usage (from repo root, with the Docker Compose stack running):

    docker compose exec api python scripts/seed_companies.py

Or with an explicit count:

    docker compose exec api python scripts/seed_companies.py --count 10000

Behaviour:
- Idempotent: checks the current row count before inserting.  If enough rows
  already exist the script exits without inserting anything.
- Inserts via SQLAlchemy Core bulk insert (one round-trip per 500-row chunk)
  to meet the < 60 second target even on a slow machine.
- Varied statuses, countries, and currencies for realistic query plans.

Spec ref: Phase 15 (T107).
"""

from __future__ import annotations

import argparse
import random
import sys
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Data pools
# ---------------------------------------------------------------------------

_STATUSES = ["pending_setup", "active", "inactive"]
_STATUS_WEIGHTS = [0.2, 0.6, 0.2]

_COUNTRIES = [
    "US",
    "GB",
    "DE",
    "FR",
    "CA",
    "AU",
    "JP",
    "SG",
    "IN",
    "BR",
    "MX",
    "NL",
    "SE",
    "NO",
    "DK",
    "FI",
    "CH",
    "ES",
    "IT",
    "PL",
    "ZA",
    "NG",
    "KE",
    "EG",
    "AE",
    "SA",
    "TR",
    "RU",
    "KR",
    "TW",
]

_CURRENCIES = [
    "USD",
    "EUR",
    "GBP",
    "JPY",
    "CAD",
    "AUD",
    "CHF",
    "SEK",
    "NOK",
    "DKK",
    "SGD",
    "INR",
    "BRL",
    "MXN",
    "ZAR",
    "HKD",
    "KRW",
    "TRY",
    "PLN",
    "AED",
]

_BUSINESS_TYPES = [
    "sole_proprietor",
    "partnership",
    "llc",
    "corporation",
    "non_profit",
    "other",
]

_CHUNK_SIZE = 500


def _make_row(n: int, owner_id: str) -> dict:
    """Build one company row dict for bulk insert."""
    now = datetime.now(UTC).isoformat()
    status = random.choices(_STATUSES, weights=_STATUS_WEIGHTS)[0]
    country = random.choice(_COUNTRIES)
    currency = random.choice(_CURRENCIES)
    slug = f"seed-company-{n:06d}"
    return {
        "id": str(uuid.uuid4()),
        "created_at": now,
        "updated_at": now,
        "legal_name": f"Seed Company {n:06d}",
        "trade_name": None,
        "slug": slug,
        "status": status,
        "owner_id": owner_id,
        "primary_admin_id": None,
        "email": f"seed{n:06d}@example.com",
        "phone_primary": None,
        "phone_secondary": None,
        "website": None,
        "tax_number": None,
        "registration_number": None,
        "business_category": None,
        "business_type": random.choice(_BUSINESS_TYPES),
        "incorporation_date": None,
        "default_currency": currency,
        "default_timezone": "UTC",
        "default_language": "en",
        "country": country,
        "fiscal_year_start_month": 1,
        "date_format": "YYYY-MM-DD",
        "number_format": "{}",
        "logo_url": None,
        "logo_previous_url": None,
        "brand_color_primary": None,
        "brand_color_secondary": None,
        "tagline": None,
        "settings": "{}",
        "metadata": "{}",
        "subscription_id": None,
        "custom_domain": None,
        "deleted_at": None,
        "deletion_reason": None,
    }


def seed(database_url: str, count: int = 10_000) -> None:
    """Insert ``count`` company rows if the table has fewer than that many rows."""
    engine = create_engine(database_url, echo=False)

    with engine.begin() as conn:
        existing: int = conn.execute(
            text("SELECT COUNT(*) FROM companies")
        ).scalar_one()
        if existing >= count:
            print(f"Already have {existing:,} companies — nothing to insert.")
            return

        to_insert = count - existing
        print(f"Inserting {to_insert:,} companies ({existing:,} already exist) …")

        # We need at least one owner user in the users table.
        owner_row = conn.execute(text("SELECT id FROM users LIMIT 1")).fetchone()
        if owner_row is None:
            print(
                "ERROR: no rows in 'users' table.\n"
                "Create at least one user first (e.g. via POST /api/v1/auth/register).",
                file=sys.stderr,
            )
            sys.exit(1)
        owner_id = str(owner_row[0])

        t0 = time.perf_counter()
        inserted = 0
        start_n = existing + 1

        # Use psycopg2 executemany via raw cursor to avoid SQLAlchemy text()
        # parameter conflicts with the '::' cast notation for custom enum types.
        raw_conn = conn.connection
        cursor = raw_conn.cursor()
        insert_sql = (
            "INSERT INTO companies ("
            "id, created_at, updated_at, legal_name, slug, status,"
            " owner_id, email, business_type, default_currency,"
            " default_timezone, default_language, country,"
            " fiscal_year_start_month, date_format, number_format,"
            " settings, metadata"
            ") VALUES ("
            "%s, %s, %s, %s, %s, %s,"
            " %s, %s, %s::businesstype, %s,"
            " %s, %s, %s,"
            " %s, %s, %s::jsonb,"
            " %s::jsonb, %s::jsonb"
            ")"
        )
        while inserted < to_insert:
            chunk_size = min(_CHUNK_SIZE, to_insert - inserted)
            rows_data = []
            for i in range(chunk_size):
                r = _make_row(start_n + inserted + i, owner_id)
                rows_data.append(
                    (
                        r["id"],
                        r["created_at"],
                        r["updated_at"],
                        r["legal_name"],
                        r["slug"],
                        r["status"],
                        r["owner_id"],
                        r["email"],
                        r["business_type"],
                        r["default_currency"],
                        r["default_timezone"],
                        r["default_language"],
                        r["country"],
                        r["fiscal_year_start_month"],
                        r["date_format"],
                        r["number_format"],
                        r["settings"],
                        r["metadata"],
                    )
                )
            cursor.executemany(insert_sql, rows_data)
            raw_conn.commit()
            inserted += chunk_size
            elapsed = time.perf_counter() - t0
            print(f"  {inserted:,}/{to_insert:,} inserted ({elapsed:.1f}s elapsed)")

        total_elapsed = time.perf_counter() - t0
        print(f"Done — {to_insert:,} companies inserted in {total_elapsed:.1f}s.")


def main() -> None:
    import os

    parser = argparse.ArgumentParser(
        description="Seed company records for performance testing."
    )
    parser.add_argument(
        "--count", type=int, default=10_000, help="Target total row count."
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="SQLAlchemy database URL (defaults to DATABASE_URL env var).",
    )
    args = parser.parse_args()

    if not args.database_url:
        print(
            "ERROR: DATABASE_URL not set and --database-url not provided.",
            file=sys.stderr,
        )
        sys.exit(1)

    seed(args.database_url, args.count)


if __name__ == "__main__":
    main()
