---
id: 0009
title: Docker Desktop full reset and route fix
stage: misc
date: 2026-08-05
surface: agent
model: claude-sonnet-5
feature: 008-accounting-finance
branch: 008-accounting-finance
user: Muhammad Amir
command: (direct instruction, no slash command)
labels: ["epic-8", "accounting", "docker", "infrastructure", "bugfix", "frontend-routing"]
links:
  spec: specs/008-accounting-finance/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/migrations/versions/034_accounting_foundation.py (down_revision fix)
 - frontend/src/app/(protected)/(purchase)/purchase/reports/** (moved from (purchase)/reports/**)
 - frontend/src/app/(protected)/(purchase)/purchase/settings/** (moved from (purchase)/settings/**)
 - frontend/src/app/(protected)/(sales)/sales/reports/** (moved from (sales)/reports/**)
 - frontend/src/app/(protected)/(sales)/sales/settings/** (moved from (sales)/settings/**)
 - frontend/src/app/(protected)/(sales)/sales/reports/page.tsx (internal href fixed)
 - specs/008-accounting-finance/tasks.md (T012/T049/T067 updated to reflect retroactive Docker verification)
tests: []
---

## Prompt

User (in Roman Urdu, over two turns): first asked "sirf yeh batao ke hum database ke liye neon postgre sql use kar rahe hain tu sqlite kiyon hai is project mai" (just tell me — we use Neon PostgreSQL for the database, so why is SQLite in this project) — answered factually (SQLite is test-only, an existing pre-Epic-8 convention; production/dev always uses Postgres; Docker being broken this session meant SQLite was the only usable test path). Then: "fix Docker Desktop yourself, try again" — an explicit instruction to resume fixing the Docker Desktop corruption that had been left unresolved since Phase 0 (where multiple non-destructive attempts — direct `docker rm`, `--remove-orphans`, `compose rm -f`, `docker desktop restart` — had all failed against the same "No such container" ghost-container error).

## Response snapshot

Escalated through several tiers of fix attempts: (1) `wsl.exe --terminate docker-desktop` + restart — fixed `docker ps -a` responsiveness but not the core corruption; (2) full `docker desktop stop` + `wsl --unregister docker-desktop` + restart — asked for and received explicit consent for a full factory reset given ~70 volumes including 3 named Postgres data volumes (erp-system, erp-system-v2, erp2) would be destroyed; discovered this didn't actually wipe anything (Docker Desktop transparently restored identical state); traced the real cause via the Windows registry (`HKCU:\...\Lxss`) to a custom data-disk location outside the default AppData path: `D:\Docker-image\DockerDesktopWSL\` containing TWO separate vhdx files — `main\ext4.vhdx` (the distro's system disk, which `wsl --unregister` DOES delete) and `disk\docker_data.vhdx` (39GB — the actual containerd/moby data store, which `wsl --unregister` does NOT touch, since it's a separately-mounted data disk, not part of the distro registration lifecycle). Deleted both while Docker Desktop was fully stopped; restart produced a genuinely empty environment (`docker compose ps -a` — the exact command broken since Phase 0 — finally worked normally).

Ran `docker compose up --build` for the first true end-to-end Postgres verification of the entire Epic 8 migration chain (001→036) and immediately caught a real bug: my own migration `034`'s `down_revision = "033"` didn't match migration `033`'s actual `revision = "033_sales_index_audit"` (a full descriptive slug, not the short numeric form used by most other migrations) — a class of bug structurally invisible to the SQLite-based test suite, which bypasses Alembic entirely via `Base.metadata.create_all()`. Fixed the reference; re-verified — all 36 migrations now apply cleanly, APScheduler initializes, "Application startup complete."

Discovered a second, unrelated pre-existing bug once the full app was live: the frontend failed to compile entirely (every route including `/login` returned 500) because `(purchase)` and `(sales)` Next.js route groups both defined bare `reports` and `settings` pages resolving to the same final URLs (`/reports`, `/settings`) — route groups don't affect the URL, so two independently-built Epics collided. Confirmed via the codebase that every OTHER module (Inventory, Companies) namespaces its pages under its own path segment (`/inventory/...`, `/companies/...`); Purchase/Sales were the only two using bare names. Asked the user whether to fix it (explicitly out of scope for "Docker fix"); given explicit approval, moved both modules' `reports`/`settings` trees under `/purchase/...` and `/sales/...` via `git mv` (preserving history), fixed the one internal link that assumed the old bare path, and verified via `grep` that no other references pointed at the old paths. Rebuilt; confirmed `/`, `/login`, `/purchase/reports`, `/sales/reports`, `/purchase-orders`, `/customers`, and the Accounting UI (`/chart-of-accounts`) all now return 200 against the live Docker stack.

Noted but did NOT fix (separate, bigger scope, flagged for later): Purchase's own reports page already contained internal links assuming a `/companies/{companyId}/purchase/reports/...` URL structure that never existed as real files — a third, independent, already-broken pattern unrelated to the collision; and all three of Purchase/Sales/my own Accounting pages read `company_id` from a `params.company_id` prop with no actual `[company_id]` dynamic route segment backing it, meaning it's always empty at runtime — a shared, pre-existing architectural gap in how company context reaches these pages (Sales' customer-import page instead reads it from `localStorage`, a third inconsistent convention). Both are pre-existing, not caused by this session's work, and were left for a separate, deliberate decision rather than expanded into silently.

## Outcome

- ✅ Impact: Docker Desktop is genuinely fixed — root cause (a corrupted 39GB `docker_data.vhdx` at a custom `D:\` location the default CLI/GUI tooling never reached) identified and resolved. Real end-to-end Postgres verification is now possible for the first time this epic, and it immediately paid for itself by catching a real migration bug my SQLite-based tests structurally could not see. A second, fully unrelated pre-existing frontend bug (blocking 100% of pages) was also found and fixed with explicit approval.
- 🧪 Tests: No new automated tests added this turn (infrastructure/bugfix work); existing accounting test suite (144 tests) and full regression (4774 tests) from the prior two phases remain the test-of-record; this session's verification was manual (`docker compose up`, `curl` against live endpoints).
- 📁 Files: 1 backend file fixed (migration 034), 15 frontend files moved via `git mv` + 1 internal link fixed, `tasks.md` updated to mark T012/T049/T067 as retroactively Docker-verified.
- 🔁 Next prompts: Two pre-existing issues flagged but deliberately not fixed: (1) Purchase's reports page has internal links to a nonexistent `/companies/{id}/purchase/reports/...` structure; (2) Purchase/Sales/Accounting pages all read `company_id` from route `params` with no actual `[company_id]` dynamic segment, so it's always empty at runtime — needs a real architectural decision (dynamic route segment vs. context vs. localStorage) rather than a silent fix. Also: the erp-system-v2 and erp2 named volumes were destroyed in the reset — if those held wanted data, it's gone (user was shown the exact volume list and explicitly confirmed twice before the reset).
- 🧠 Reflection: The corruption was invisible to every tool operating at the Docker API layer (`docker rm`, `compose rm`, engine restart, even WSL distro unregister/re-register) because the real persistent store was a second, separately-mounted data disk at a non-default location — tracing it required going around the `docker` CLI entirely and querying the Windows WSL registry directly. This is a good example of a bug where the fix requires understanding the tool's actual architecture (Docker Desktop's WSL2 backend uses two disks, not one) rather than retrying the same category of command with more force.

## Evaluation notes (flywheel)

- Failure modes observed: (1) `wsl --unregister <distro>` only deletes disks that are part of that distro's own registration — separately-mounted data disks (common in Docker Desktop's WSL2 architecture: a small system disk + a large data disk) survive unregister/re-register cycles and must be located and deleted independently. (2) Migration `down_revision` values must reference the exact `revision` string of the prior file, not an assumed numeric shorthand — worth grep-checking the actual prior file's `revision =` line before writing a new migration's `down_revision`, rather than inferring the convention from an arbitrary earlier example.
- Graders run and results (PASS/FAIL): N/A.
- Prompt variant (if applicable): N/A.
- Next experiment (smallest change to try): Before writing any future migration's `down_revision`, `grep -n "^revision" migrations/versions/<prior-file>.py` first rather than assuming the short-numeric convention holds — this session showed it doesn't always (026, 033 use full descriptive slugs).
