# Sales Management — Developer Quickstart

**Epic 7 — Sales Management**
**Date**: 2026-07-30

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
  -d '{"email":"sales@example.com","password":"Secret1!","company_name":"Acme Corp"}'

# Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sales@example.com","password":"Secret1!"}' | jq -r '.data.access_token')

# All sales API calls require:
#   Authorization: Bearer $TOKEN
#   company_id in path: /api/v1/companies/{company_id}/sales/...
COMPANY_ID="<uuid-from-register-response>"
BASE="http://localhost:8000/api/v1/companies/$COMPANY_ID/sales"
```

---

## 3. Health Check

```bash
curl -H "Authorization: Bearer $TOKEN" $BASE/health
# => {"data":{"status":"healthy","module":"sales","version":"1.0.0"},"message":"..."}
```

---

## 4. Create a Customer Category

```bash
curl -X POST $BASE/customer-categories \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "RETAIL",
    "name": "Retail Customers",
    "default_credit_limit": 0
  }'
```

---

## 5. Create a Customer

```bash
curl -X POST $BASE/customers \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_code": "CUST-001",
    "legal_name": "Test Customer Ltd",
    "customer_type": "COMPANY",
    "category_id": "<category-uuid>",
    "currency_code": "USD",
    "credit_limit": 50000.00
  }'
CUSTOMER_ID="<customer-uuid>"
```

---

## 6. Add Contact and Address (Required for Activation)

```bash
# Add primary contact
curl -X POST $BASE/customers/$CUSTOMER_ID/contacts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "contact_name": "John Smith",
    "email": "john@testcustomer.com",
    "is_primary": true,
    "is_billing_contact": true
  }'

# Add billing address
curl -X POST $BASE/customers/$CUSTOMER_ID/addresses \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "address_type": "BOTH",
    "address_line_1": "123 Business St",
    "city": "New York",
    "country_code": "US",
    "is_default_billing": true,
    "is_default_shipping": true
  }'
```

---

## 7. Activate Customer

```bash
curl -X POST $BASE/customers/$CUSTOMER_ID/activate \
  -H "Authorization: Bearer $TOKEN"
# Customer is now ACTIVE and eligible for transactions
```

---

## 8. Create a Sales Order

```bash
curl -X POST $BASE/sales-orders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "'$CUSTOMER_ID'",
    "order_date": "2026-07-30",
    "currency_code": "USD",
    "priority": "NORMAL",
    "lines": [
      {
        "product_id": "<product-uuid-from-epic5>",
        "description": "Widget A",
        "quantity_ordered": 10,
        "unit_of_measure": "PCS",
        "unit_price": 25.00
      }
    ]
  }'
ORDER_ID="<order-uuid>"
```

---

## 9. Submit and Approve the Order

```bash
# Submit for approval
curl -X POST $BASE/sales-orders/$ORDER_ID/submit \
  -H "Authorization: Bearer $TOKEN"

# Approve (requires approval permission)
curl -X POST $BASE/sales-orders/$ORDER_ID/approve \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"comments": "Approved for delivery"}'
```

---

## 10. Create and Dispatch Delivery Note

```bash
# Create delivery note
curl -X POST $BASE/delivery-notes \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "'$ORDER_ID'",
    "lines": [
      {
        "order_line_id": "<order-line-uuid>",
        "quantity_dispatched": 10
      }
    ]
  }'
DN_ID="<dn-uuid>"

# Dispatch (reserves and deducts stock via Epic 5)
curl -X POST $BASE/delivery-notes/$DN_ID/dispatch \
  -H "Authorization: Bearer $TOKEN"
```

---

## 11. Generate Invoice

```bash
curl -X POST $BASE/invoices/from-delivery-note \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"delivery_note_id": "'$DN_ID'"}'
INVOICE_ID="<invoice-uuid>"

# Issue the invoice
curl -X POST $BASE/invoices/$INVOICE_ID/issue \
  -H "Authorization: Bearer $TOKEN"
```

---

## 12. Complete O2C Cycle

At this point, you have completed the full Order-to-Cash cycle:
1. Customer created and activated
2. Sales Order created, submitted, and approved
3. Delivery Note created and dispatched (stock deducted)
4. Invoice generated and issued

The Sales Order is now in INVOICED status and can be closed:

```bash
curl -X POST $BASE/sales-orders/$ORDER_ID/close \
  -H "Authorization: Bearer $TOKEN"
```

---

## API Reference

| Resource | Base Path | Key Operations |
|----------|-----------|----------------|
| Customers | `$BASE/customers` | CRUD, activate, block, search |
| Customer Categories | `$BASE/customer-categories` | CRUD |
| Customer Groups | `$BASE/customer-groups` | CRUD |
| Quotations | `$BASE/quotations` | CRUD, send, accept, convert |
| Sales Orders | `$BASE/sales-orders` | CRUD, submit, approve, cancel |
| Delivery Notes | `$BASE/delivery-notes` | Create, dispatch, cancel |
| Invoices | `$BASE/invoices` | Create, issue, cancel |
| Sales Returns | `$BASE/sales-returns` | CRUD, submit, approve, receive |
| Price Lists | `$BASE/price-lists` | CRUD with entries |
| Discount Rules | `$BASE/discount-rules` | CRUD |
| Reports | `$BASE/reports/{type}` | Read with filters |
| KPIs | `$BASE/kpis` | Dashboard data |
