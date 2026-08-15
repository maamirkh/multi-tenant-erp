"""AccountingScheduler — APScheduler integration for background jobs.

Registers daily jobs at FastAPI startup (research.md Decision 13):
  - ``recurring_journal_job``     — executes due recurring journal templates
  - ``ar_ap_overdue_check_job``   — flags overdue AR transactions (AP half no-op)
  - ``ap_bill_due_reminder_job``  — publishes upcoming-bill-due reminders (Phase 7)

``recurring_journal_job`` wired to real logic as of Phase 5 —
``RecurringJournalService.execute_due_templates()``. ``ar_ap_overdue_check_job``'s
AR half wired as of Phase 6 — ``AccountsReceivableService.run_overdue_check()``;
its AP half remains a documented no-op (tasks.md never asks for an AP
"overdue" job — only the due-*soon* reminder below). ``ap_bill_due_reminder_job``
wired to real logic as of Phase 7 — ``AccountsPayableService.
run_bill_due_reminder_check()``.

In-process only (no Redis/Celery) per research.md Decision 13 — consistent
with the ``InProcessEventBus`` pattern used throughout the platform.

Spec ref: specs/008-accounting-finance/tasks.md T036, T118, T166
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

#: Module-level scheduler singleton — created on startup, shut down on exit.
_scheduler: BackgroundScheduler | None = None


def recurring_journal_job() -> None:
    """Execute due recurring journal templates.

    Runs outside any FastAPI request — builds its own ``Session`` via
    ``SessionLocal`` (mirrors ``handlers/integration_handlers.py``'s
    pattern) and always closes it, even on failure. One template's
    failure does not stop the others — ``RecurringJournalService.
    execute_due_templates()`` already records per-template FAILED
    instances internally rather than raising.
    """
    from core.database.session import SessionLocal
    from modules.accounting.dependencies import build_recurring_journal_service

    db = SessionLocal()
    try:
        service = build_recurring_journal_service(db)
        instances = service.execute_due_templates()
        logger.info(
            "recurring_journal_job: processed %d due template(s)", len(instances)
        )
    except Exception:  # noqa: BLE001 — a scheduler job must never crash the process
        logger.exception("recurring_journal_job: unexpected failure")
    finally:
        db.close()


def ar_ap_overdue_check_job() -> None:
    """Flag overdue AR/AP transactions and publish overdue/warning events.

    AR half wired to real logic as of Phase 6 —
    ``AccountsReceivableService.run_overdue_check()``. The AP half remains
    a documented no-op: AP transaction tables don't exist until Phase 7.
    """
    from datetime import date

    from core.database.session import SessionLocal
    from modules.accounting.dependencies import build_ar_service

    db = SessionLocal()
    try:
        service = build_ar_service(db, with_sales_sync=False)
        summary = service.run_overdue_check(as_of_date=date.today())
        db.commit()
        logger.info(
            "ar_ap_overdue_check_job: marked %d transaction(s) OVERDUE, "
            "published %d credit-limit warning(s); AP half is a no-op until Phase 7",
            summary["overdue_count"],
            summary["warning_count"],
        )
    except Exception:  # noqa: BLE001 — a scheduler job must never crash the process
        db.rollback()
        logger.exception("ar_ap_overdue_check_job: unexpected failure")
    finally:
        db.close()


def ap_bill_due_reminder_job() -> None:
    """Publish ``accounting.ap.bill.due`` for every open bill due within the
    configured lookahead window (default 7 days — tasks.md T166).

    Runs outside any FastAPI request — builds its own ``Session`` via
    ``SessionLocal`` and always closes it, even on failure, mirroring
    ``recurring_journal_job``/``ar_ap_overdue_check_job``'s pattern.
    """
    from datetime import date

    from core.database.session import SessionLocal
    from modules.accounting.dependencies import build_ap_service

    db = SessionLocal()
    try:
        service = build_ap_service(db)
        summary = service.run_bill_due_reminder_check(as_of_date=date.today())
        db.commit()
        logger.info(
            "ap_bill_due_reminder_job: published %d bill-due reminder(s)",
            summary["due_count"],
        )
    except Exception:  # noqa: BLE001 — a scheduler job must never crash the process
        db.rollback()
        logger.exception("ap_bill_due_reminder_job: unexpected failure")
    finally:
        db.close()


def start_scheduler(hour: int = 1, minute: int = 0) -> BackgroundScheduler:
    """Create, configure, and start the accounting background scheduler.

    Idempotent: calling this more than once returns the existing running
    scheduler instance rather than creating a second one.

    Args:
        hour:   Hour of day (UTC, 24h) both jobs run at. Configurable so
                tests and deployments can avoid overlapping with other
                maintenance windows.
        minute: Minute of the hour both jobs run at.

    Returns:
        The running ``BackgroundScheduler`` instance.
    """
    global _scheduler  # noqa: PLW0603

    if _scheduler is not None and _scheduler.running:
        return _scheduler

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        recurring_journal_job,
        trigger=CronTrigger(hour=hour, minute=minute),
        id="accounting_recurring_journal_job",
        replace_existing=True,
    )
    scheduler.add_job(
        ar_ap_overdue_check_job,
        trigger=CronTrigger(hour=hour, minute=minute),
        id="accounting_ar_ap_overdue_check_job",
        replace_existing=True,
    )
    scheduler.add_job(
        ap_bill_due_reminder_job,
        trigger=CronTrigger(hour=hour, minute=minute),
        id="accounting_ap_bill_due_reminder_job",
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "Accounting scheduler started: recurring_journal_job, "
        "ar_ap_overdue_check_job, and ap_bill_due_reminder_job registered "
        "at %02d:%02d UTC daily",
        hour,
        minute,
    )
    return scheduler


def shutdown_scheduler() -> None:
    """Stop the accounting background scheduler, if running."""
    global _scheduler  # noqa: PLW0603
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Accounting scheduler stopped")
    _scheduler = None


def get_scheduler() -> BackgroundScheduler | None:
    """Return the active scheduler instance, or None if not started."""
    return _scheduler
