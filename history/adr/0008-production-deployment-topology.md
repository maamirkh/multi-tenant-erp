# ADR-0008: Production Deployment Topology

- **Status:** Accepted
- **Date:** 2026-10-09
- **Deciders:** Project owner (sole maintainer)
- **Feature:** 012-production-readiness
- **Supersedes:** Constitution v1.2.1 §6.6 "Initial Deployment" (Vercel / Render / Neon), and `docs-project-context/DECISIONS.md` ADR-018 "Deployment Strategy" (a non-canonical legacy record)
- **Context:** Three documents disagreed about where production runs (Epic 12 G-01):
  - Constitution §6.6 named Vercel + Render + Neon;
  - `DECISIONS.md` ADR-018 named Vercel + a Docker VPS;
  - `DEPLOYMENT_GUIDE.md` recommended Hetzner.

  The repository already builds a production backend image (`backend/Dockerfile`; uvicorn with workers) and a standalone Next.js frontend (`output: 'standalone'`). No staging or production environment exists. The owner approved Option B as Epic 12 decision D-01.

<!-- Significance checklist: Impact ✅ (platform/ops/cost), Alternatives ✅, Scope ✅ -->

## Decision

| Layer | Choice |
|---|---|
| Frontend | Vercel |
| Backend | Dockerized FastAPI on a VPS. Migrations run as a single release job; the scheduler runs as a dedicated process with a PostgreSQL advisory lock (D-09). |
| Database | Managed PostgreSQL |
| File storage | Private, tenant-scoped, S3-compatible object storage with short-lived signed URLs (D-04) |
| Email | Transactional email provider (D-05) |

**Providers and regions are not chosen here.** The Epic 12 plan compares them on:
- backup and point-in-time recovery (PITR);
- TLS;
- latency to users;
- cost;
- operational burden.

Nothing is purchased before that comparison. The service objectives in Epic 12 are **proposed, not an SLA**:
- RPO ≤ 1 h;
- RTO ≤ 4 h;
- 99.5% monthly availability.

The plan must show they are feasible on the chosen providers.

The Constitution §6.6 "Future Growth Path" (CDN/WAF, dedicated hosts, Redis) is kept. Each part of it is adopted only with measured evidence (NFR-PRD-09).

## Consequences

### Positive

- Reuses the existing Docker image and the standalone frontend build.
- A managed database moves backups, PITR and patching to the provider.
- A single VPS keeps cost and operations within reach of one maintainer.

### Negative

- A single VPS is a single point of failure for the API. The RTO and availability objectives must account for it, through a documented rebuild runbook and image-based redeploys.
- Three to four external providers must be operated and monitored.
- The frontend and API live on different origins, so CSP, CORS and cookie decisions must allow for that.

## Alternatives Considered

- **A — Render (PaaS) + Neon, as in the old §6.6:** less operational work, but less control over workers, scheduler processes and cost at scale. The owner chose B.
- **C — Self-hosted everything on a VPS (Hetzner + Compose + self-managed PostgreSQL):** lowest cost, but backups, PITR and patching fall on a single maintainer. That risks RPO/RTO.
- **Kubernetes or microservices:** rejected as premature (Constitution §5, §50).

## Reasoning

B balances control over the backend runtime, which the D-09 runtime-safety rules need, against moving the riskiest operational duty — the database — to a managed provider. It fits an SME-scale, single-maintainer launch.

## References

- Constitution v2.0.0 §6.6
- Spec: `specs/012-production-readiness/spec.md` (D-01, D-02, D-04, D-05, D-07, D-09)
- `docs-project-context/DECISIONS.md` ADR-018; `docs-project-context/DEPLOYMENT_GUIDE.md`
