"""Re-exports the shared ``crm_client`` fixture for this directory.

Standard pytest convention: a ``conftest.py``-level re-export (rather than
importing the fixture directly into each test module) avoids every test
function's ``crm_client`` parameter reading as an ``F811`` redefinition
of a module-level import to static analysis tools, while still making
the fixture available to every test file in this directory via pytest's
normal ``conftest.py`` discovery.

Task: T096 (tasks.md Phase 10).
"""

from __future__ import annotations

from tests.integration.api.v1.crm.conftest import crm_client

__all__ = ["crm_client"]
