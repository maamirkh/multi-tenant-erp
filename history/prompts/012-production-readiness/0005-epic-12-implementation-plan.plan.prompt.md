---
id: 0005
title: Epic 12 Implementation Plan
stage: plan
date: 2026-10-09
surface: agent
model: claude-opus-5-5
feature: 012-production-readiness
branch: 012-production-readiness
user: Muhammad Amir
command: /sp.plan
labels: ["epic-12", "plan", "deployment", "production-readiness", "security", "backup", "observability", "ci-cd"]
links:
  spec: specs/012-production-readiness/spec.md
  ticket: null
  adr: history/adr/0008-production-deployment-topology.md
  pr: null
files:
  - specs/012-production-readiness/plan.md
tests:
  - none (planning only)
---

## Prompt

# Epic 12 — Deployment / Production Readiness: Implementation Plan

Create the complete `plan.md` for the approved Epic 12 specification using the existing Spec-Kit Plus workflow.

## 1. Mandatory Preflight Gate

Before planning, inspect the current Git branch/status and verify that the governance PR containing Constitution v2.0.0 and ADR-0007, ADR-0008, and ADR-0009 has actually merged into `main`.

* If it has not merged, STOP. Do not create or modify `plan.md`. Report the exact missing prerequisite.
* If merged, verify the current `main` contains the approved amendments and that the specification and governance documents agree.
* The official Epic title MUST be exactly `Epic 12 — Deployment / Production Readiness`.
* Read the current Constitution, canonical ADRs, Epic 12 `spec.md`, `clarifications.md`, amendment package, repository architecture, CI workflows, and relevant Epic 0–11 implementation plans.
* Follow the repository's actual Spec-Kit Plus conventions. Do not invent commands, paths, providers, existing capabilities, or completed work.

## 2. Planning Rules

This is a planning-only task. Do not implement application code, create migrations, install packages, deploy infrastructure, provision paid services, modify runtime configuration, or generate `tasks.md`.

Preserve the existing modular monolith and working ERP behavior. Prefer the simplest maintainable solution for Pakistan SMEs. Justify every new service or dependency by security, reliability, or measurable operational benefit.

## 3. Required Plan Coverage

Create a phased, dependency-aware implementation plan covering:

1. Environment separation, secret management, production configuration guardrails, Docker hardening, and runtime/migration role separation.
2. Dedicated migration release job, schema-head readiness checks, and safe rollback/expand-contract strategy.
3. Single scheduler process, PostgreSQL advisory locking, atomic recurring-journal/GL posting, and concurrent multi-process tests.
4. Immediate session/access-token revocation, CSP, shared authentication rate limiting, auth security, and platform-admin/tenant boundary tests. Retain in-house JWT; do not implement Better Auth unless new evidence demonstrates the approved design cannot be secured and the owner explicitly approves reconsideration.
5. Private tenant-scoped object storage, signed/authorized access, upload validation, SVG removal, and real transactional email with safe failure/retry behavior.
6. Logging, error tracking, metrics, readiness/liveness, external uptime probes, alerting, and incident correlation.
7. CI-required branch protection, build/test/security/image scanning, deployment pipeline, staging, smoke tests, and rollback rehearsal. Never bypass failing required checks.
8. Managed PostgreSQL, VPS, object-storage, email, DNS/TLS, monitoring and uptime-provider comparisons. Compare cost, regional latency, backups/PITR, security, reliability, lock-in, and operational burden. Do not assume a provider or purchase services.
9. Backup/restore and archive design, least-privilege DB roles, 30-day operational backup retention, and the provisional seven-year business-record retention requirement.
10. PostgreSQL-backed tenant-isolation/RBAC/IDOR suite; RLS remains deferred unless evidence justifies it.
11. Production-like performance/load baselines, including Epic 11 report/export limits and latency, with memory and timeout measurements.
12. Runbooks for deployment, rollback, restoration, incidents, secret rotation, migration recovery, storage/email failure, and scheduler recovery.
13. Staging drills, first production deployment, smoke tests, and the evidence-based production-readiness gate.

## 4. Explicit Targets and Open Inputs

Carry these targets into the plan without presenting unproven objectives as guarantees:

* RPO ≤ 1 hour, verified by restore drill.
* RTO ≤ 4 hours, verified by recovery drill.
* Proposed 99.5% monthly availability; assess feasibility and cost before any SLA.
* Operational backup retention: 30 days initially.
* Business/accounting retention: seven years as a planning assumption, pending professional/legal confirmation.
* D-10 workload numbers remain owner-supplied. Define the benchmark method and clearly mark provisional thresholds; do not invent tenant, user, invoice, or concurrency figures.

Provider selection, sender domain, legal retention confirmation, and workload figures may remain open during planning if the specification permits, but must be resolved before the final production-readiness gate.

## 5. Architecture, Sequence, and Evidence

For every phase specify:

* Goal and requirements covered (exact FR-PRD, SEC, DB, SC, and performance IDs).
* Concrete repository areas/files expected to change, based on inspection.
* Dependencies and safe implementation order.
* Tests, CI checks, PostgreSQL integration tests, staging drills, and evidence artifacts required.
* Rollback/recovery strategy and security risks.
* Acceptance criteria and measurable exit gate.

Order work so that foundational configuration and safe runtime execution precede staging; staging precedes recovery/security/performance drills; production deployment occurs only after all MUST requirements have evidence.

Protect Epic 11 contracts, tenant isolation, accounting integrity, report/export behavior, audit-before-delivery, and existing API compatibility.

## 6. Deliverables and Stop Conditions

Produce only the complete `plan.md`, following the repository's established template. Include a phase/dependency overview, risk register, verification strategy, external decisions, and a traceability matrix mapping every MUST requirement to a planned phase and evidence.

Do not create tasks or implement anything. After writing the plan, audit it against the full specification for missing requirements, dependency cycles, unjustified complexity, unsupported assumptions, and untestable acceptance criteria.

Report the plan's location, phases, requirement coverage, unresolved inputs, and any blockers. Declare readiness for task generation only if the plan is complete and consistent with the approved specification.

## Response snapshot

**Preflight passed:** PR #10 is merged (`e0f45d4`), the Constitution is at 2.0.0, ADR-0007/0008/0009 exist and the official title is in place. Some spec status lines still describe the governance change as pending; this is non-blocking and was noted, not edited.

`plan.md` (~1100 lines) contains:
- 15 key design decisions (P-1…P-15);
- a provider-comparison framework with no prices or picks;
- data-model and interface deltas;
- the owner inputs;
- 14 phases (P0–P13) with an acyclic dependency graph;
- a verification strategy and a risk register;
- a full MUST traceability matrix, a self-audit, and ADR suggestions.

Newly evidenced defects:
- the recurring posting commits twice (`posting_engine.py:624`, then `base.py:84`), leaving a duplicate-GL crash window;
- uvicorn runs without proxy-header trust, so all clients would share one login rate-limit bucket behind the proxy;
- path-filtered workflows cannot serve as required checks (PR #10 ran only Summary and GitGuardian).

Spec tensions surfaced:
- FR-PRD-005 vs FR-PRD-023 (N-1 rollback) → an operator override;
- 99.5% (3.6 h/month) vs a 4 h RTO, and provider-loss RPO → owner decisions.

**Verdict:** ready for `/sp.tasks`. Not run.

## Outcome

- ✅ Impact: an evidence-gated, provider-neutral production plan; no implementation.
- 🧪 Tests: none (planning).
- 📁 Files: `specs/012-production-readiness/plan.md`.
- 🔁 Next prompts: `/sp.tasks`, plus owner inputs §9 #1, #5 and #6 by the end of P0.
- 🧠 Reflection: code inspection found three defects that the spec had not captured.

## Evaluation notes (flywheel)

- Failure modes observed: the separate research, data-model and contracts artifacts were skipped and folded into `plan.md`, per the owner's "only plan.md" instruction; the agent-context script was skipped for the same reason.
- Graders run and results (PASS/FAIL): self-audit §16 — PASS.
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
