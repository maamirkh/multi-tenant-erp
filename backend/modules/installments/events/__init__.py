"""Installments domain events.

**Deliberately NOT an in-process ``EventBus``** (unlike
``modules/crm/events/__init__.py`` / ``modules/sales/events/__init__.py`` /
``modules/accounting/events/__init__.py`` / ``modules/purchase/events/__init__.py``'s
identical in-process-bus pattern, which does not persist events and loses
them on process restart). Installments is money-adjacent (payment
schedules, delinquency, late charges), where silently losing an event is
a worse outcome than in, say, a CRM lead-status-changed notification.
Installments-owned events are published via the existing transactional
outbox (``core/events/outbox.py``) instead, so a published event and its
originating business mutation always commit together or not at all
(Constitution §49, ADR-INST-09).

Nothing to define yet in Phase 1 (module foundation) — event
payload/schema definitions are added here starting the first phase that
actually needs to publish one.

Spec ref: specs/010-installments/plan.md §26.
"""

from __future__ import annotations
