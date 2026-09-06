# Purchase Management — Developer Quickstart

**Epic 6 — Purchase Management**
**Phase 10 — Integration Foundation**
**Date**: 2026-07-29

---

## Prerequisites

- Docker + Docker Compose installed
- Python 3.12 + Poetry (backend)
- Node.js 20+ (frontend)
- PostgreSQL reachable (via Docker or local)

---

## 1. Start the Stack

```bash
# From repo root
docker compose up --build

# Verify services
curl http://localhost:8000/health           # API
curl http://localhost:3000                 # Frontend
```

---

## 2. Authenticate

```bash
# Create a company + user via Auth API (Epic 2)
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"pm@example.com","password":"Secret1!","company_name":"Acme Corp"}'

# Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"pm@example.com","password":"Secret1!"}' | jq -r '.data.access_token')

# All purchase API calls require:
#   Authorization: Bearer $TOKEN
#   company_id in path: /api/v1/companies/{company_id}/purchase/...
COMPANY_ID="<uuid-from-register-response>"
BASE="http://localhost:8000/api/v1/companies/$COMPANY_ID/purchase"
```

---

## 3. Health Check

```bash
curl -H "Authorization: Bearer $TOKEN" $BASE/health
# => {"data":{"status":"healthy","module":"purchase","version":"1.0.0"},"message":"..."}
```

---

## 4. Supplier Master — Core Workflow

### 4a. Create a Supplier (starts in DRAFT)

```bash
SUPPLIER=$(curl -s -X POST $BASE/suppliers \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "legal_name": "Global Parts Ltd",
    "trade_name": "Global Parts",
    "supplier_code": "SUP-001",
    "supplier_type": "MANUFACTURER",
    "tax_id": "GB123456789",
    "currency_code": "USD",
    "payment_terms_days": 30
  }')

SUPPLIER_ID=$(echo $SUPPLIER | jq -r '.data.id')
echo "Supplier: $SUPPLIER_ID"
```

### 4b. Activate Supplier

```bash
curl -X POST $BASE/suppliers/$SUPPLIER_ID/activate \
  -H "Authorization: Bearer $TOKEN"
# status transitions: DRAFT → ACTIVE
```

### 4c. Add Contact

```bash
curl -X POST $BASE/suppliers/$SUPPLIER_ID/contacts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Smith",
    "email": "j.smith@globalparts.com",
    "phone": "+44-20-1234-5678",
    "is_primary": true
  }'
```

### 4d. Bulk Import Suppliers (CSV)

```bash
# Requires purchase.bulk_import_suppliers feature flag (enabled by default)
curl -X POST $BASE/suppliers/import \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@suppliers.csv"
# CSV columns: legal_name,supplier_code,supplier_type,tax_id,currency_code,payment_terms_days
```

---

## 5. Purchase Request Workflow

### 5a. Create PR

```bash
PR=$(curl -s -X POST $BASE/purchase-requests \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Office Supplies Q1",
    "department": "ADMIN",
    "required_date": "2026-09-01",
    "reason_code": "OPERATIONAL"
  }')
PR_ID=$(echo $PR | jq -r '.data.id')
```

### 5b. Add Lines

```bash
curl -X POST $BASE/purchase-requests/$PR_ID/lines \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "A4 Paper Reams",
    "quantity": "10.000",
    "unit_of_measure": "BOX",
    "estimated_unit_price": "12.50"
  }'
```

### 5c. Submit for Approval

```bash
curl -X POST $BASE/purchase-requests/$PR_ID/submit \
  -H "Authorization: Bearer $TOKEN"
# status: DRAFT → PENDING_APPROVAL
```

### 5d. Approve PR

```bash
curl -X POST $BASE/purchase-requests/$PR_ID/approve \
  -H "Authorization: Bearer $TOKEN"
# status: PENDING_APPROVAL → APPROVED
# Event: purchase_request.approved published on InProcessEventBus
```

---

## 6. Purchase Order Workflow

### 6a. Create PO (from approved PR)

```bash
PO=$(curl -s -X POST $BASE/purchase-requests/$PR_ID/convert-to-po \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "supplier_id": "'$SUPPLIER_ID'",
    "expected_delivery_date": "2026-09-15"
  }')
PO_ID=$(echo $PO | jq -r '.data.id')
```

### 6b. Or Create PO directly (requires `purchase.direct_po_allowed`)

```bash
# Enable feature flag first:
curl -X PUT $BASE/feature-flags/purchase.direct_po_allowed \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'

PO=$(curl -s -X POST $BASE/purchase-orders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "supplier_id": "'$SUPPLIER_ID'",
    "expected_delivery_date": "2026-09-15"
  }')
PO_ID=$(echo $PO | jq -r '.data.id')
```

### 6c. Add Lines + Charges, Submit, Approve

```bash
# Add line
curl -X POST $BASE/purchase-orders/$PO_ID/lines \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "A4 Paper Reams",
    "quantity": "10.000",
    "unit_of_measure": "BOX",
    "unit_price": "11.80"
  }'

# Add freight charge
curl -X POST $BASE/purchase-orders/$PO_ID/charges \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"charge_type": "FREIGHT", "amount": "25.00", "description": "Courier freight"}'

# Submit
curl -X POST $BASE/purchase-orders/$PO_ID/submit \
  -H "Authorization: Bearer $TOKEN"

# Approve (triggers purchase.po_email_supplier stub if flag enabled)
curl -X POST $BASE/purchase-orders/$PO_ID/approve \
  -H "Authorization: Bearer $TOKEN"
```

### 6d. Export PO as PDF

```bash
curl -H "Authorization: Bearer $TOKEN" \
  $BASE/purchase-orders/$PO_ID/export/pdf \
  -o po-export.pdf
```

---

## 7. Goods Receipt Workflow

### 7a. Check Open Quantities

```bash
curl -H "Authorization: Bearer $TOKEN" \
  $BASE/purchase-orders/$PO_ID/open-quantities
# Returns per-line open quantities to populate GR form
```

### 7b. Create + Confirm GR

```bash
GR=$(curl -s -X POST $BASE/goods-receipts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "po_id": "'$PO_ID'",
    "received_date": "2026-09-15",
    "lines": [
      {"po_line_id": "<line-uuid>", "quantity_received": "10.000", "quantity_rejected": "0.000"}
    ]
  }')
GR_ID=$(echo $GR | jq -r '.data.id')

# Confirm (atomic: updates stock, PO status, supplier rating)
curl -X POST $BASE/goods-receipts/$GR_ID/confirm \
  -H "Authorization: Bearer $TOKEN"
# Events published: purchase.gr.confirmed, purchase.cost.recorded
# PO status → FULLY_RECEIVED
```

### 7c. Barcode Scan for GR (stub — requires feature flag)

```bash
# Enable flag
curl -X PUT $BASE/feature-flags/purchase.gr_barcode_scan \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'

# Lookup (returns 501 until Epic 5 wired)
curl -H "Authorization: Bearer $TOKEN" \
  $BASE/goods-receipts/barcode/1234567890123
```

---

## 8. Vendor Return (RMA) Workflow

```bash
# Create RMA against confirmed GR
RMA=$(curl -s -X POST $BASE/vendor-returns \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "gr_id": "'$GR_ID'",
    "return_reason": "DAMAGED",
    "notes": "3 reams arrived water damaged",
    "lines": [
      {"gr_line_id": "<gr-line-uuid>", "return_quantity": "3.000"}
    ]
  }')
RMA_ID=$(echo $RMA | jq -r '.data.id')

curl -X POST $BASE/vendor-returns/$RMA_ID/submit -H "Authorization: Bearer $TOKEN"
curl -X POST $BASE/vendor-returns/$RMA_ID/approve -H "Authorization: Bearer $TOKEN"
curl -X POST $BASE/vendor-returns/$RMA_ID/dispatch -H "Authorization: Bearer $TOKEN"
curl -X POST $BASE/vendor-returns/$RMA_ID/complete -H "Authorization: Bearer $TOKEN"
# Final event: purchase.rma.completed (credit_note_pending=true)
```

---

## 9. Reports & KPIs

```bash
# All 10 KPIs
curl -H "Authorization: Bearer $TOKEN" "$BASE/reports/kpis?date_from=2026-01-01&date_to=2026-12-31"

# PO Summary (supports ?fmt=csv or ?fmt=xlsx for export)
curl -H "Authorization: Bearer $TOKEN" "$BASE/reports/purchase-order-summary?fmt=csv" -o po-summary.csv

# Supplier Performance
curl -H "Authorization: Bearer $TOKEN" "$BASE/reports/supplier-performance"

# Purchase Price Variance
curl -H "Authorization: Bearer $TOKEN" "$BASE/reports/purchase-price-variance"

# All 14 report endpoints:
# purchase-order-summary, pending-purchase-orders, overdue-deliveries,
# goods-receipt-report, purchase-request-status, supplier-performance,
# vendor-return-report, purchase-by-supplier, purchase-by-category,
# purchase-price-variance, open-purchase-commitments, purchase-trend-analysis,
# goods-rejection-analysis, procurement-audit-trail
```

---

## 10. Feature Flags

```bash
# List all flags
curl -H "Authorization: Bearer $TOKEN" $BASE/feature-flags

# Flags enabled by default:
#   purchase.approval_required_pr    — PR must be approved
#   purchase.approval_required_po    — PO must be approved
#   purchase.approval_required_rma   — RMA must be approved
#   purchase.credit_limit_check      — WARN on PO approval if over limit
#   purchase.over_receipt_warn       — WARN on GR over-receipt
#   purchase.bulk_import_suppliers   — CSV bulk supplier import
#   purchase.bulk_export_purchase    — CSV/Excel export
#   purchase.purchase_reporting      — All 14 reports + KPIs

# Flags disabled by default (require explicit activation):
#   purchase.direct_po_allowed       — Create PO without prior PR
#   purchase.ppv_alerts              — PPV threshold notifications
#   purchase.po_email_supplier       — Email PO to supplier on approval (stub)
#   purchase.gr_barcode_scan         — Barcode lookup for GR line entry (stub)
#   purchase.supplier_portal         — Future: supplier self-service portal
#   purchase.ai_procurement_assistant — Future: AI demand prediction

# Toggle a flag
curl -X PUT $BASE/feature-flags/purchase.direct_po_allowed \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

---

## 11. Domain Events — Subscribing

```python
# In your module or test fixture
from modules.purchase.events import get_event_bus

captured = []
get_event_bus().subscribe("supplier.created", lambda e: captured.append(e.to_dict()))
get_event_bus().subscribe("*", lambda e: print(f"EVENT: {e.event_type} [{e.aggregate_id}]"))
```

See `specs/006-purchase-management/contracts/events.md` for the full event catalogue (33 events).

---

## 12. Running Tests

```bash
cd backend

# All purchase tests
poetry run pytest tests/unit/modules/purchase/ tests/integration/api/v1/purchase/ tests/integration/repositories/purchase/ -v

# Domain events coverage (68 tests)
poetry run pytest tests/unit/modules/purchase/test_all_events_coverage.py -v

# Phase 10 specific
poetry run pytest tests/integration/api/v1/purchase/test_supplier_import.py -v
poetry run pytest tests/integration/api/v1/purchase/test_po_export.py -v

# All tests with coverage
poetry run pytest --cov=modules/purchase --cov-report=term-missing
```

---

## 13. API Contract Reference

- **OpenAPI spec**: `specs/006-purchase-management/contracts/purchase-v1.yaml`
- **Domain events**: `specs/006-purchase-management/contracts/events.md`
- **Data model**: `specs/006-purchase-management/data-model.md`
- **Full spec**: `specs/006-purchase-management/spec.md`
- **Implementation plan**: `specs/006-purchase-management/plan.md`

---

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| 403 `Feature ... not enabled` | Feature flag disabled | Enable via `PUT /feature-flags/{key}` |
| 409 `Supplier already exists` | Duplicate supplier_code | Use unique supplier_code |
| 422 `PO not in APPROVED status` | GR against non-approved PO | Approve PO first |
| 501 `Barcode lookup stub` | `gr_barcode_scan` enabled but Epic 5 not wired | Expected — integration pending |
| 422 `Over-receipt detected` | GR qty > PO open qty | Check `purchase.over_receipt_warn` policy |
