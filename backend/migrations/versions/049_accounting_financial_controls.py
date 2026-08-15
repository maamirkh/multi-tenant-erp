"""Financial Controls & Audit Trail — Phase 14 (tasks.md T272-T285).

- Adds ``accounting.*`` RBAC permissions (21 codes, spec.md §33 Permission
  Matrix) to the global ``permissions`` catalogue and maps them onto every
  EXISTING company's EXISTING system roles via ``role_permissions``, using
  the same idempotent (skip-if-present) approach
  ``RoleSeedService.seed_permissions()``/``seed_role_permissions()`` already
  use for new companies (constants.py's ``DEFAULT_ROLE_PERMISSIONS`` is the
  single source of truth this migration mirrors in raw SQL — migrations in
  this codebase don't import application code, matching every prior
  migration's convention).
- Adds ``'REJECTED'`` to ``accounting_payments.status``'s CHECK constraint,
  and two nullable reconstruction columns (``advance_account_id``,
  ``wht_payable_account_id``) needed by ``PaymentService.approve_payment()``
  to rebuild the GL lines of a payment that was held DRAFT pending approval
  (T274) — see payments.py model docstrings for the full rationale.
- Adds audit-log query indexes for the new ``GET /accounting/audit-log``
  endpoint (T279) and the composite GL index tasks.md T280 calls for.

Spec ref: specs/008-accounting-finance/tasks.md T277, T280
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "049"
down_revision = "048"
branch_labels = None
depends_on = None


_PERMISSIONS = [
    (
        "accounting.gl.view",
        "View General Ledger",
        "accounting",
        "read",
        "View GL entries and balances",
    ),
    (
        "accounting.journal.create",
        "Create Journal Entry",
        "accounting",
        "create",
        "Create a manual journal entry",
    ),
    (
        "accounting.journal.approve",
        "Approve Journal Entry",
        "accounting",
        "approve",
        "Approve a journal entry submitted for approval",
    ),
    (
        "accounting.journal.post",
        "Post Journal Entry",
        "accounting",
        "update",
        "Post a draft/approved journal entry to the GL",
    ),
    (
        "accounting.journal.reverse",
        "Reverse Journal Entry",
        "accounting",
        "update",
        "Reverse a posted journal entry",
    ),
    (
        "accounting.period.lock",
        "Lock/Unlock Period",
        "accounting",
        "manage",
        "Lock or unlock a fiscal period",
    ),
    (
        "accounting.period.close",
        "Close Fiscal Year",
        "accounting",
        "manage",
        "Close a fiscal year",
    ),
    (
        "accounting.payment.customer.create",
        "Create Customer Payment",
        "accounting",
        "create",
        "Record a customer payment receipt",
    ),
    (
        "accounting.payment.customer.approve",
        "Approve Customer Payment",
        "accounting",
        "approve",
        "Approve a customer payment submitted for approval",
    ),
    (
        "accounting.payment.supplier.create",
        "Create Supplier Payment",
        "accounting",
        "create",
        "Record a supplier payment disbursement",
    ),
    (
        "accounting.payment.supplier.approve",
        "Approve Supplier Payment",
        "accounting",
        "approve",
        "Approve a supplier payment submitted for approval",
    ),
    (
        "accounting.coa.manage",
        "Manage Chart of Accounts",
        "accounting",
        "manage",
        "Create/update/deactivate accounts",
    ),
    (
        "accounting.tax.manage",
        "Manage Tax Codes",
        "accounting",
        "manage",
        "Create/update tax codes, rates, and groups",
    ),
    (
        "accounting.exchangerate.manage",
        "Manage Exchange Rates",
        "accounting",
        "manage",
        "Record exchange rates and run currency revaluation",
    ),
    (
        "accounting.bank.reconcile",
        "Perform Bank Reconciliation",
        "accounting",
        "update",
        "Reconcile bank statements",
    ),
    (
        "accounting.reports.view",
        "View Financial Statements",
        "accounting",
        "read",
        "View trial balance, balance sheet, P&L, cash flow, and subsidiary reports",
    ),
    (
        "accounting.ar.writeoff",
        "Write-Off AR",
        "accounting",
        "manage",
        "Write off an uncollectible AR balance",
    ),
    (
        "accounting.creditlimit.override",
        "Override Credit Limit",
        "accounting",
        "manage",
        "Override a customer's credit hold/limit",
    ),
    (
        "accounting.approvalworkflow.manage",
        "Manage Approval Workflows",
        "accounting",
        "manage",
        "Configure journal/payment approval thresholds",
    ),
    (
        "accounting.audit.view",
        "View Audit Trail",
        "accounting",
        "read",
        "View the full financial audit trail",
    ),
]

# Mirrors constants.py's DEFAULT_ROLE_PERMISSIONS accounting additions.
_ROLE_PERMISSION_CODES = {
    "owner": [
        "accounting.gl.view",
        "accounting.journal.create",
        "accounting.journal.approve",
        "accounting.journal.post",
        "accounting.journal.reverse",
        "accounting.period.lock",
        "accounting.period.close",
        "accounting.payment.customer.create",
        "accounting.payment.customer.approve",
        "accounting.payment.supplier.create",
        "accounting.payment.supplier.approve",
        "accounting.coa.manage",
        "accounting.tax.manage",
        "accounting.exchangerate.manage",
        "accounting.bank.reconcile",
        "accounting.reports.view",
        "accounting.ar.writeoff",
        "accounting.creditlimit.override",
        "accounting.approvalworkflow.manage",
        "accounting.audit.view",
    ],
    "admin": [
        "accounting.gl.view",
        "accounting.period.close",
        "accounting.reports.view",
        "accounting.approvalworkflow.manage",
        "accounting.audit.view",
    ],
    "manager": [
        "accounting.gl.view",
        "accounting.journal.create",
        "accounting.journal.approve",
        "accounting.journal.post",
        "accounting.journal.reverse",
        "accounting.period.lock",
        "accounting.payment.customer.create",
        "accounting.payment.customer.approve",
        "accounting.payment.supplier.create",
        "accounting.payment.supplier.approve",
        "accounting.coa.manage",
        "accounting.tax.manage",
        "accounting.exchangerate.manage",
        "accounting.bank.reconcile",
        "accounting.reports.view",
        "accounting.ar.writeoff",
        "accounting.creditlimit.override",
        "accounting.audit.view",
    ],
    "accountant": [
        "accounting.gl.view",
        "accounting.journal.create",
        "accounting.journal.post",
        "accounting.coa.manage",
        "accounting.exchangerate.manage",
        "accounting.bank.reconcile",
        "accounting.reports.view",
    ],
    "salesperson": ["accounting.payment.customer.create", "accounting.reports.view"],
    "cashier": [
        "accounting.payment.customer.create",
        "accounting.payment.supplier.create",
    ],
    "viewer": [
        "accounting.gl.view",
        "accounting.reports.view",
        "accounting.audit.view",
    ],
}


def upgrade() -> None:
    conn = op.get_bind()

    # --- Permission catalogue (global, idempotent) -----------------------
    for perm_id, label, module, action, description in _PERMISSIONS:
        conn.execute(
            sa.text(
                "INSERT INTO permissions (id, code, label, module, action, description) "
                "VALUES (:id, :code, :label, :module, :action, :description) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {
                "id": perm_id,
                "code": perm_id,
                "label": label,
                "module": module,
                "action": action,
                "description": description,
            },
        )

    # --- Role-permission mappings for every EXISTING company's EXISTING
    # system roles (idempotent — ON CONFLICT DO NOTHING matches the
    # (role_id, permission_id) unique constraint). New companies created
    # after this migration get these via RoleSeedService as normal.
    for slug, codes in _ROLE_PERMISSION_CODES.items():
        for code in codes:
            conn.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id) "
                    "SELECT r.id, :code FROM roles r "
                    "WHERE r.slug = :slug AND r.is_system = true "
                    "ON CONFLICT (role_id, permission_id) DO NOTHING"
                ),
                {"code": code, "slug": slug},
            )

    # --- Payment approval workflow (T274) support -------------------------
    op.drop_constraint(
        "ck_accounting_payments_status", "accounting_payments", type_="check"
    )
    op.create_check_constraint(
        "ck_accounting_payments_status",
        "accounting_payments",
        "status IN ('DRAFT','POSTED','ALLOCATED','CANCELLED','REJECTED')",
    )
    op.add_column(
        "accounting_payments",
        sa.Column(
            "advance_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounting_accounts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.add_column(
        "accounting_payments",
        sa.Column(
            "wht_payable_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounting_accounts.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )

    # --- Audit log query indexes (T279 GET /accounting/audit-log) --------
    # NOTE: ix_accounting_audit_log_company_entity (company_id, entity_type,
    # entity_id) and a single-column occurred_at index already exist from
    # migration 038 (Phase 4) — only add what's genuinely new here.
    op.create_index(
        "ix_accounting_audit_log_company_occurred_at",
        "accounting_audit_log",
        ["company_id", "occurred_at"],
    )
    op.create_index(
        "ix_accounting_audit_log_actor",
        "accounting_audit_log",
        ["actor_user_id"],
    )

    # --- GL aggregation composite index (T280) ----------------------------
    # NOTE: tasks.md T280 asks for a composite index on
    # accounting_journal_lines(company_id, fiscal_period_id, account_id) —
    # but fiscal_period_id lives on accounting_journal_entries, not on the
    # lines table (verified against the live schema). The equivalent,
    # already-covering index ix_accounting_journal_lines_company_account
    # (company_id, account_id) was added in migration 048 alongside
    # accounting_journal_entries(company_id, posting_date) — together they
    # already serve the report queries this index would have targeted, so
    # no new index is added here rather than creating one against a
    # nonexistent column.


def downgrade() -> None:
    # NOTE (Phase 18, T315): no drop_index for
    # "ix_accounting_journal_lines_company_period_account" here — upgrade()
    # never creates it (see the T280 comment above); a stray drop_index
    # call for it was removed as part of T315's bi-directional migration
    # verification (it would fail with "index does not exist" on a
    # genuinely fresh database).
    op.drop_index("ix_accounting_audit_log_actor", table_name="accounting_audit_log")
    op.drop_index(
        "ix_accounting_audit_log_company_occurred_at", table_name="accounting_audit_log"
    )
    op.drop_column("accounting_payments", "wht_payable_account_id")
    op.drop_column("accounting_payments", "advance_account_id")
    op.drop_constraint(
        "ck_accounting_payments_status", "accounting_payments", type_="check"
    )
    op.create_check_constraint(
        "ck_accounting_payments_status",
        "accounting_payments",
        "status IN ('DRAFT','POSTED','ALLOCATED','CANCELLED')",
    )
    # Permission/role_permission rows are intentionally left in place on
    # downgrade — removing them could delete permissions already relied on
    # by roles a user configured after upgrading (same convention as no
    # prior migration in this codebase reversing seed data).
