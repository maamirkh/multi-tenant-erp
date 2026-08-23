"""HealthService — the platform operational health view (T174,
FR-9A-240/241, US-11).

Surfaces the same underlying checks `/api/v1/health` already computes
(database connectivity, auth configuration) plus outbox pending/
published counts — never a second, divergent health-check
implementation. Each check independently reports its own status; a
failed check renders `unavailable`/`degraded` with its own name, never a
fabricated `ok` or a blanket "unknown" (FR-9A-243, matching T172's
dashboard-widget honesty principle applied to health checks).

**Relay honesty (FR-9A-241)**: this codebase has no message-bus relay —
`OutboxRecord` rows are written but nothing consumes them yet
(structured-logging-only, plan.md's own documented state). The health
view labels this explicitly as a logging-only stub rather than implying
real message-bus delivery is occurring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from core.config.settings import Settings
from core.events.outbox import EventOutboxRepository


@dataclass(frozen=True)
class PlatformHealth:
    """The assembled platform health result."""

    status: str
    """"healthy" or "degraded" — degraded if any check below is not ok."""
    checks: dict[str, str]
    outbox_pending: int
    outbox_published: int
    relay: dict[str, Any]


class HealthService:
    """Domain service for the platform operational health view."""

    def __init__(
        self, db: Session, outbox_repo: EventOutboxRepository, settings: Settings
    ) -> None:
        self._db = db
        self._outbox_repo = outbox_repo
        self._settings = settings

    def get_health(self) -> PlatformHealth:
        checks: dict[str, str] = {}
        overall = "healthy"

        try:
            self._db.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except OperationalError:
            checks["database"] = "unavailable"
            overall = "degraded"

        try:
            jwt_ok = (
                bool(self._settings.JWT_SECRET_KEY)
                and len(self._settings.JWT_SECRET_KEY) >= 32
                and bool(self._settings.JWT_ALGORITHM)
            )
            checks["auth_config"] = "ok" if jwt_ok else "misconfigured"
            if not jwt_ok:
                overall = "degraded"
        except Exception:  # noqa: BLE001
            checks["auth_config"] = "unavailable"
            overall = "degraded"

        try:
            outbox_pending = self._outbox_repo.count_pending()
            outbox_published = self._outbox_repo.count_published()
            checks["outbox"] = "ok"
        except OperationalError:
            checks["outbox"] = "unavailable"
            overall = "degraded"
            outbox_pending = 0
            outbox_published = 0

        return PlatformHealth(
            status=overall,
            checks=checks,
            outbox_pending=outbox_pending,
            outbox_published=outbox_published,
            relay={
                "status": "logging_only_stub",
                "note": (
                    "No message-bus relay is integrated in this Epic — outbox "
                    "rows are written and counted here, but nothing consumes "
                    "them yet. This is not real message-bus delivery."
                ),
            },
        )
