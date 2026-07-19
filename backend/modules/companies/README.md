# Companies Module

## Purpose and Scope

The Companies module implements the full multi-tenant company lifecycle for the DevSphere ERP platform. Each authenticated user can own one or more companies. All ERP data (invoices, inventory, etc.) is scoped to a company.

**In scope:**
- Company CRUD with status lifecycle management
- Soft delete and restore with retention window
- Address management (registered, mailing, billing, shipping)
- Company settings (structured key/value configuration)
- Company branding (logo upload via S3-compatible storage)
- Audit log (immutable, append-only record of all changes)
- Domain events via transactional outbox pattern

**Out of scope (future epics):**
- Role-based access control within companies (Epic 4)
- Multi-user membership (Epic 4)
- Billing and subscription management

---

## Layer Overview

```
modules/companies/
├── models/               # SQLAlchemy ORM models
│   ├── company.py        # Company aggregate root
│   ├── company_address.py
│   ├── company_audit_log.py
│   └── enums.py          # CompanyStatus, AddressType
├── repositories/         # Persistence layer (DB access only)
│   ├── company_repository.py
│   ├── company_address_repository.py
│   └── company_audit_log_repository.py
├── services/             # Business logic layer
│   ├── company_service.py          # Core lifecycle operations
│   ├── company_settings_service.py # Settings whitelist + validation
│   └── company_logo_service.py     # S3 upload, MIME validation
├── schemas/              # Pydantic request/response models
│   ├── company.py
│   ├── company_address.py
│   └── company_audit_log.py
├── router.py             # FastAPI route handlers (thin controllers)
├── dependencies.py       # FastAPI dependency injection wiring
├── events.py             # Domain event definitions and outbox writer
├── exceptions.py         # Module-specific exception types
└── validators.py         # Reusable field validators (E.164, ISO codes)
```

### Layer Rules

| Layer | Responsibility | May Import |
|-------|---------------|-----------|
| `router.py` | Parse request, call service, return response | Services, Schemas, Dependencies |
| `services/` | Business rules and orchestration | Repositories, Events, Exceptions |
| `repositories/` | DB queries and persistence | Models only |
| `events.py` | Write outbox records | Models, DB session |

Routes must never contain SQL queries or business decisions. Repositories must never contain `if/else` business logic.

---

## Key Business Rules

| Rule | Description |
|------|-------------|
| BR-001 | `legal_name` must be globally unique (case-insensitive) |
| BR-002 | `slug` is derived from `legal_name` and immutable after first activation |
| BR-003 | A user may own at most 5 companies simultaneously |
| BR-008 | Activation requires `country` (ISO 3166-1 alpha-2) and `default_currency` (ISO 4217) |
| BR-010 | Soft-deleted companies are retained for `COMPANY_DELETION_RETENTION_DAYS` days (default: 30) |
| BR-011 | The audit log is append-only; the DB user has no `UPDATE`/`DELETE` on `company_audit_logs` |

### Status Transition Table

```
pending_setup  →  active
active         →  inactive | deleted
inactive       →  active | deleted
deleted        →  inactive  (restore)
suspended      →  (no owner transitions — admin only)
```

---

## How to Add a New Settings Key to `ALLOWED_SETTINGS`

Settings are validated against a whitelist in `services/company_settings_service.py`.

1. Open `backend/modules/companies/services/company_settings_service.py`.
2. Add an entry to the `ALLOWED_SETTINGS` dict:

```python
ALLOWED_SETTINGS: dict[str, tuple[type, list[Any] | None]] = {
    # ... existing keys ...

    # New key: restrict to allowed values
    "new_feature_mode": (str, ["basic", "advanced"]),

    # New key: any string value accepted
    "custom_footer_text": (str, None),

    # New key: any integer value accepted
    "max_invoice_line_items": (int, None),
}
```

3. The key is immediately available via `PATCH /api/v1/companies/{id}/settings`.
4. Add a unit test in `tests/unit/companies/test_company_settings_service.py` for the new key.

No migration is required — settings are stored as a JSONB column on the `companies` table.

---

## How to Add a New Audit Event Type

Audit events are written by `CompanyService` in `services/company_service.py`.

1. Choose an `action` string in `SCREAMING_SNAKE_CASE` (e.g., `"COMPANY_TRANSFERRED"`).
2. In the relevant service method, call `self._audit_repo.create(...)` after the state change:

```python
self._audit_log_repo.create(
    db,
    company_id=company.id,
    actor_id=owner_id,
    action="COMPANY_TRANSFERRED",
    before_state=before_snapshot,
    after_state=after_snapshot,
)
```

3. Add the action string to the `action` filter enum in `schemas/company_audit_log.py` if it should appear in the filter dropdown.
4. Add an integration test asserting the audit record is written.

---

## How to Add a New Status Transition

Status transitions are defined in `_VALID_TRANSITIONS` near the top of `company_service.py`.

1. Add the new target status to the appropriate source set:

```python
_VALID_TRANSITIONS: dict[str, set[str]] = {
    CompanyStatus.inactive.value: {
        CompanyStatus.active.value,
        CompanyStatus.deleted.value,
        CompanyStatus.archived.value,  # ← new target
    },
    # ...
}
```

2. Add the corresponding enum value to `models/enums.py` and the DB check constraint in the migration.
3. Add a service method that calls `self._assert_owner_transition(company, CompanyStatus.archived.value)`.
4. Add a route and integration tests.

---

## Known Limitations

- **RBAC is simplified** — all authenticated company owners have full control over their companies. Role-based permissions within a company (admin, manager, accountant, etc.) are planned for Epic 4. The permission matrix in `spec.md §8.2` is enforced in tests but the role enum is not yet populated by company membership.
- **Single owner** — each company has exactly one owner (`owner_id`). Multi-owner or team ownership is an Epic 4 concern.
- **No background worker** — domain events are written to `event_outbox` but no background processor dispatches them to message queues. The outbox table is the handoff point; a future Epic will add the dispatcher.

---

## Future Enhancements

- Outbox event dispatcher (background worker → message broker)
- Company membership and team roles (Epic 4)
- Company suspension workflow (admin-initiated, not owner-initiated)
- Bulk import / CSV seeding endpoint
- Permanent deletion sweep job for expired soft-deleted records
