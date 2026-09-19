"""Importing this module registers every domain catalog exactly once,
populating ``REPORT_REGISTRY``/``ADAPTER_REGISTRY`` in full (Gate 2,
T125: 43 ``NOW`` + 3 ``DEFERRED`` entries).

Deliberately **not** done in ``registry/__init__.py`` itself: every
catalog imports from ``modules.reports.services.adapters.base``, which in
turn imports ``modules.reports.registry.definitions`` — a sibling module
in this same package. Python always finishes running a package's own
``__init__.py`` before any of its submodules, so an eager catalog import
there would deadlock ``base.py``'s own import of ``registry.definitions``
partway through package initialization (a genuine circular import,
caught by actually running the full Reports test suite after wiring this
up the first way). This plain, ordinary submodule sidesteps that
entirely — it is only ever imported explicitly, by code that actually
needs the complete registry (Gate-2/3/4/5 verification tests today; the
real app's discovery/execution wiring from Phase 3 onward), never as a
side effect of importing anything more foundational.
"""

from __future__ import annotations

from modules.reports.registry import (
    catalog_accounting as catalog_accounting,
)
from modules.reports.registry import (
    catalog_crm as catalog_crm,
)
from modules.reports.registry import (
    catalog_crossmodule as catalog_crossmodule,
)
from modules.reports.registry import (
    catalog_executive as catalog_executive,
)
from modules.reports.registry import (
    catalog_installments as catalog_installments,
)
from modules.reports.registry import (
    catalog_inventory as catalog_inventory,
)
from modules.reports.registry import (
    catalog_purchase as catalog_purchase,
)
from modules.reports.registry import (
    catalog_sales as catalog_sales,
)
