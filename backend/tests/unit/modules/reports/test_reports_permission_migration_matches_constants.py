"""T037 — migration ``075_reports_permission_seed.py``'s literal
``_PERMISSIONS`` tuple exactly matches ``REPORTS_PERMISSIONS``
(``modules/users_roles/constants.py``) — catches catalog/migration drift
at **test time**, never at migration-run time.
"""

from __future__ import annotations

import importlib

from modules.users_roles.constants import REPORTS_PERMISSIONS

_migration = importlib.import_module("migrations.versions.075_reports_permission_seed")


def test_migration_literal_tuple_matches_constants_exactly() -> None:
    migration_set = set(_migration._PERMISSIONS)
    constants_set = {
        (p.code, p.label, p.action, p.description) for p in REPORTS_PERMISSIONS
    }
    assert migration_set == constants_set


def test_migration_and_constants_both_have_16_codes() -> None:
    assert len(_migration._PERMISSIONS) == 16
    assert len(REPORTS_PERMISSIONS) == 16
