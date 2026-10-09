---
id: 0002
title: Epic 12 Clarification Decisions
stage: spec
date: 2026-10-08
surface: agent
model: claude-opus-5-5
feature: 012-production-readiness
branch: 012-production-readiness
user: Muhammad Amir
command: /sp.clarify
labels: ["epic-12", "clarify", "decisions", "governance", "deployment"]
links:
  spec: specs/012-production-readiness/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - history/prompts/012-production-readiness/0002-epic-12-clarification-decisions.spec.prompt.md
tests:
  - none
---

## Prompt

# Epic 12 — Deployment / Production Readiness — Clarification

You are working on the existing DevSphere ERP SaaS repository.

The authoritative Epic name is:
**Epic 12 — Deployment / Production Readiness**

We already created the Epic 12 spec.md. Do NOT implement code, migrations, deployment configuration, or infrastructure yet. This step is ONLY to resolve the open decisions identified by the spec so the specification can become implementation-ready.

## Mandatory workflow

Read the Constitution, DECISIONS.md, DEPLOYMENT_GUIDE.md, Epic 11 final documents, and the current Epic 12 spec.md. Preserve approved architecture and terminology unless a contradiction requires an explicit decision. Do not silently choose between conflicting documents.

The spec identified 14 existing production controls that must NOT be rebuilt and 22 implementation gaps. Treat existing controls as baseline evidence and focus clarification on decisions/gaps.

## Decisions to clarify

### D-01 — Production architecture

Existing documents conflict:

* Constitution §6.6: Vercel + Render + Neon
* ADR-018: Vercel + Docker VPS
* DEPLOYMENT_GUIDE.md: Hetzner

Present the exact options, trade-offs, costs/operational complexity, security, scalability, and fit for the SME target. Include the current recommendation:
**Vercel frontend + Dockerized FastAPI backend on VPS + managed PostgreSQL**, but do not finalize it without approval. Identify the required Constitution/ADR updates.

### D-02 — RPO

Ask for the acceptable maximum data-loss window and translate the selected value into backup requirements. Do not invent a business target.

### D-03 — Retention

Resolve the conflict between the 30-day deployment-guide backup retention and the 7-year accounting/business retention. Clearly distinguish operational backup retention from legal/accounting/business data retention where applicable.

### D-04 — File storage

Production logo/avatar uploads currently are not properly wired and storage URLs may be public. Clarify the approved production storage model, privacy/access model, URL strategy, allowed file types/size, and tenant isolation.

### D-05 — Email

Password reset/email verification are currently stubbed. Clarify whether Epic 12 must provide real transactional email, the approved provider/configuration approach, delivery/security requirements, and local-development behavior.

### D-06 — Governance

Constitution requires a develop branch and second-engineer review, while actual workflow is solo-owner + Claude Code + PR/admin bypass. Recommend a realistic solo-owner model: protected main, PR required, CI required, one owner approval where applicable, no unsafe bypass. State exactly what Constitution/ADR text must change.

### D-07 — Availability/RTO

Ask for acceptable availability target and maximum recovery time. Translate approved targets into operational requirements; do not invent SLA numbers.

### D-08 — CSP/Auth

ADR-0003 accepted refresh-token localStorage conditional on CSP, but current frontend does not provide CSP. Present options: implement the required CSP safely, or revisit the token-storage decision. Explain security and compatibility implications. Do not weaken the security requirement.

### D-09 — Runtime safety

Clarify/confirm production rules for:

* migrations must not run independently in every worker;
* recurring scheduler must have exactly one safe execution mechanism;
* duplicate journal posting must be prevented and proven with a production-like test/drill;
* DEBUG, default MinIO credentials, wildcard CORS and similar unsafe settings must fail closed before production.

Recommend safe defaults but do not implement them yet.

### D-10 — SME workload

Ask for business-approved initial and near-term capacity assumptions: tenants, users/company, concurrent users, transaction volume, report/export volume and growth horizon. Do not invent numbers. Use approved assumptions later for performance acceptance criteria.

## Additional mandatory clarification

Review all 22 identified gaps and classify each as:

1. Epic 12 MUST,
2. SHOULD,
3. DEFERRED,
4. Already satisfied/no implementation.

Identify dependencies between decisions and gaps. Specifically flag anything that blocks production readiness.

## Constitution changes

For D-01 and D-06, provide exact proposed amendment intent and affected sections, but do NOT edit the Constitution yet. Changes require explicit owner approval.

## Output

Return:

1. Decision table D-01–D-10 with options, recommendation, rationale, and required owner decision.
2. 22-gap classification.
3. Production blockers.
4. Constitution/ADR amendment list.
5. Any remaining contradictions.
6. Exact questions requiring my answers.
7. A final statement of whether Epic 12 is ready for `/sp.plan`.

Do NOT create tasks. Do NOT implement anything. Do NOT silently resolve business decisions.

## Response snapshot

The response contains:
- a decision table for D-01…D-10, with options, a recommendation and the owner decision each one needs;
- the 22 gaps classified: 19 MUST (13 of them production blockers), 2 SHOULD (G-16 partial, G-17), 1 already accepted (G-22);
- decision-to-gap dependencies;
- amendment intent for Constitution §6.6, §28, §29, §43 and §44 #13, and a new ADR for the deployment topology;
- remaining contradictions: §6.3 Better Auth vs ADR-0001; §24 Black vs Ruff; §28 "merge commits for releases" vs the squash-only ruleset; two separate ADR series (`DECISIONS.md` vs `history/adr`);
- 10 exact owner questions.

Verdict: NOT ready for `/sp.plan` until the owner answers. The spec was not modified, because no answers have been accepted yet.

New findings from re-inspection:
- company logos allow `image/svg+xml`, which is an XSS risk once served publicly;
- Inventory export returns a `/dev/exports/...` placeholder URL when storage is missing.

## Outcome

- ✅ Impact: every decision is framed for the owner; nothing was resolved silently.
- 🧪 Tests: none.
- 📁 Files: this PHR only (the spec will be updated once answers arrive).
- 🔁 Next prompts: owner answers to Q1–Q10, then a spec update (Clarifications section plus decision integration), then `/sp.plan`.
- 🧠 Reflection: cost figures were kept qualitative or flagged for verification, rather than invented.

## Evaluation notes (flywheel)

- Failure modes observed: none.
- Graders run and results (PASS/FAIL): n/a
- Prompt variant (if applicable): `/sp.clarify` run as a batch decision report, at the user's request.
- Next experiment (smallest change to try): n/a
