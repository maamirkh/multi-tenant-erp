# Research: Epic 5 – Inventory Management

**Phase**: Phase 0 — Architecture Research & Decision Resolution
**Date**: 2026-07-20
**Branch**: `005-inventory-management`
**Spec**: [spec.md](./spec.md)

---

## Purpose

This document resolves all architectural decisions required before Epic 5 implementation begins. Each decision is informed by the approved spec.md, the Engineering Constitution, and patterns established in Epics 1–4.

---

## Research Area 1: Inventory Domain Layering within Modular Monolith

**Question**: How should the Inventory domain be structured within DevSphere ERP's modular monolith to enforce separation of concerns, enable independent testing, and support downstream module consumption without coupling?

**Decision**: Strict Clean Architecture layering within the `inventory` module boundary.

```
inventory/
  domain/          ← Entities, Value Objects, Domain Events, Aggregate Roots
  application/     ← Use Cases, DTOs, Service interfaces
  infrastructure/  ← Repository implementations, ORM models, file storage adapters
  api/             ← FastAPI routers, request/response schemas, auth middleware
```

**Rationale**:
- Consistent with the Clean Architecture pattern established across Epics 1–4
- Domain layer has zero dependency on FastAPI, SQLAlchemy, or any external framework
- Application layer orchestrates domain operations and publishes events — no direct DB access
- Infrastructure layer is the only layer that touches PostgreSQL via SQLAlchemy
- API layer is the only entry point for external callers (HTTP) and injects dependencies

**Alternatives considered**:
- **Transaction Script (rejected)**: Business logic would bleed into services without domain encapsulation; violates DDD intent
- **Active Record (rejected)**: Couples domain logic to ORM; prevents unit testing without database

---

## Research Area 2: Stock Position Calculation Strategy — Derived vs Stored

**Question**: Should the current stock position (per product per warehouse) be stored as a materialised value that is updated with every movement, or always derived from the sum of all ledger entries?

**Decision**: **Hybrid approach** — store a materialised position snapshot alongside the immutable ledger.

**Rationale**:
- A pure-ledger approach (sum all entries on every query) becomes unacceptably slow as ledger grows beyond tens of thousands of entries per product
- A pure-materialised approach risks inconsistency if an update fails after the ledger entry is committed (or vice versa)
- Hybrid: the ledger is the source of truth; the materialised position is updated within the same database transaction as the ledger entry (atomic); the position can always be recalculated from the ledger for audit/reconciliation
- This satisfies Business Invariant INV-001 from the spec while meeting the p95 < 300ms performance target

**Consistency guarantee**: Both the ledger entry and the position update are committed atomically. If the transaction rolls back, neither is persisted.

**Alternatives considered**:
- **Pure ledger (rejected)**: Meets integrity requirements but fails the 300ms performance target for high-volume companies
- **Pure materialised (rejected)**: Fast but creates reconciliation risk; violated SSOT principle

---

## Research Area 3: Inventory Costing Method — WAC vs FIFO Implementation Strategy

**Question**: Given that both WAC and FIFO must be supported but a company selects one at setup, how should the costing calculation be structured to support both without code duplication?

**Decision**: **Strategy Pattern** for cost calculation — a costing strategy is selected per company at runtime and applied uniformly to all stock-out movements.

- WAC strategy: recalculates and stores the weighted average unit cost on every stock-in movement; applies this cost to stock-out movements
- FIFO strategy: maintains a FIFO cost queue per product per warehouse; pops the oldest cost layer on each stock-out movement

**Rationale**:
- Encapsulates costing logic independently of the stock movement workflow
- Adding future costing methods (LIFO, Standard Cost, Specific Identification) requires only a new strategy implementation
- Company's selected strategy is loaded once per request from the company configuration; no conditional branching throughout the ledger code

**Migration risk**: The constitution mandates that the costing method must not change mid-period without a formal revaluation event. A "Revaluation Event" movement type is reserved in the ledger for this purpose.

---

## Research Area 4: Domain Event Publishing — Synchronous vs Asynchronous

**Question**: Should domain events (ProductCreated, StockIncreased, etc.) be published synchronously within the request lifecycle or dispatched asynchronously to a queue/bus?

**Decision**: **Synchronous in-process event bus for Epic 5**, with architecture designed for seamless upgrade to async messaging (Redis Streams, Kafka, or RabbitMQ) in a future Epic.

**Rationale**:
- Epic 1's infrastructure does not yet include a production message broker
- In-process publishing is reliable, simple, and sufficient for Epic 5's scope (consuming modules are not yet implemented)
- The event bus interface is abstracted — domain code publishes to an interface; the underlying transport (in-process vs Redis Streams) is swappable without domain changes
- All domain events are serialisable (JSON) from day one, ready for async dispatch
- This matches the Engineering Constitution's §49 Event-Driven Communication Principles

**Alternatives considered**:
- **Async Redis Streams immediately (deferred)**: Adds infrastructure complexity before the event consumers (Purchase, Sales, Accounting) exist; premature optimisation
- **No events at all (rejected)**: Violates the spec's cross-module contract requirements and forces downstream modules to poll

---

## Research Area 5: Multi-Tenant Isolation Enforcement Strategy

**Question**: How should company_id (tenant) isolation be enforced for Inventory operations, given the volume of queries involved?

**Decision**: **Repository-level isolation** — every repository method receives the company_id as a mandatory first-class argument; a base repository class enforces that all queries include a `WHERE company_id = ?` clause automatically.

**Rationale**:
- Pattern established in Epics 2–4; consistent with the Engineering Constitution §9 Multi-Tenant Principles
- No service-level company_id injection needed — the repository layer is the enforcement boundary
- Unit tests can verify isolation by testing that repositories reject queries without company_id
- No risk of "company_id forgetting" — compile-time (type system) and runtime enforcement combined

**Alternatives considered**:
- **Row-level security in PostgreSQL (not selected as primary)**: Powerful but adds DB-level complexity; not used in previous Epics; reserved as defence-in-depth layer
- **Service-level injection (rejected)**: Too many places to enforce; easy to miss

---

## Research Area 6: Product Search Implementation

**Question**: How should full-text product search be implemented to meet the < 500ms requirement at scale?

**Decision**: **PostgreSQL Full-Text Search (FTS) with tsvector** as the primary search mechanism, supplemented by trigram indexes (pg_trgm) for partial-match and typo-tolerant search.

**Rationale**:
- PostgreSQL FTS is already available in the existing infrastructure (no new dependency)
- tsvector columns on product name, code, SKU, description, and keywords are updated via triggers or application-side on write
- pg_trgm extension enables similarity search (handles typos, partial matches)
- For barcode/SKU/code search, exact-match B-tree indexes are sufficient and sub-100ms
- This avoids introducing Elasticsearch or a dedicated search service at this stage

**Future path**: If search latency degrades beyond 500ms at high product counts (>200K products), an Elasticsearch or OpenSearch index can be layered on top of the existing full-text structure without changing the domain model.

---

## Research Area 7: File Storage — Product Images

**Question**: How should product image storage be handled?

**Decision**: Consistent with Epic 3 (Companies logos on S3). Product images are stored in the company's S3-compatible bucket under a `/products/` prefix, following the File Storage Principles in the Engineering Constitution §33.

- Primary image and gallery images stored per product and per variant
- Thumbnails generated on upload (resize to standard dimensions)
- Image metadata (path, size, content type) stored in the database; actual files in S3
- CDN-ready: all image URLs are pre-signed S3 URLs or public CDN URLs depending on bucket policy

---

## Research Area 8: Audit Trail Implementation

**Question**: How should the inventory audit trail be implemented without creating a performance bottleneck on every write operation?

**Decision**: **Synchronous audit write within the same database transaction** as the primary write operation, using a shared audit schema established in earlier Epics.

**Rationale**:
- Atomic consistency: if the primary write fails, the audit entry is not committed either
- Performance: a single additional INSERT per operation is negligible; p95 targets remain achievable
- The audit table is write-only from the application layer — no update or delete endpoints exist
- Separate audit schema prevents accidental JOINs with operational data

**Alternatives considered**:
- **Async audit (rejected)**: Creates a gap between the operation and its audit record; violates the spec's 100% audit completeness requirement
- **Change Data Capture via DB triggers (deferred)**: More robust but adds infrastructure complexity; reserved as an upgrade path

---

## Research Area 9: Feature Toggle Implementation

**Question**: How should the feature flag system work for inventory capabilities marked "Ready but Disabled" or "Future"?

**Decision**: **Company-scoped feature flag table** in the database, loaded at request time as part of company context, following the Feature Toggles pattern in the Engineering Constitution §11.

- Feature flags are Boolean per company, keyed by a string constant (e.g., `inventory.adjustment_approval`, `inventory.overstock_alerts`)
- Default values are defined in code (constitution's "Ready but Disabled" defaults)
- Company Admin can toggle flags within their permitted set; Platform Admin can toggle all flags
- Service layer checks the flag before executing gated capabilities; a missing flag defaults to the system default

---

## Research Area 10: Bulk Import Strategy

**Question**: How should bulk product import (up to 10,000 rows) be handled to meet the < 60 seconds requirement without blocking the application?

**Decision**: **Background task processing** via FastAPI's BackgroundTasks or a lightweight task queue (Celery + Redis worker), with progress tracked in the database and result delivered via notification.

- Upload triggers immediate validation of file format and size
- Processing runs in the background; user receives a job_id immediately
- Import job status is queryable (pending → processing → completed / failed_with_errors)
- Row-level errors are collected and returned in the job result
- On completion, an ImportCompleted or ImportFailed notification is sent (in-app + email)

---

## Resolution Summary

| Decision | Resolution |
| --- | --- |
| Domain layering | Clean Architecture within inventory module boundary |
| Stock position | Hybrid: materialised position + immutable ledger (atomic) |
| Costing method | Strategy Pattern (WAC / FIFO pluggable at company level) |
| Domain events | Synchronous in-process bus (async-ready architecture) |
| Tenant isolation | Repository-level mandatory company_id enforcement |
| Product search | PostgreSQL FTS + tsvector + pg_trgm |
| Image storage | S3-compatible bucket following Epic 3 patterns |
| Audit trail | Synchronous write within same transaction |
| Feature flags | Company-scoped DB table, loaded at request time |
| Bulk import | Background task with job tracking and notifications |

**All NEEDS CLARIFICATION items resolved. Phase 1 design may proceed.**
