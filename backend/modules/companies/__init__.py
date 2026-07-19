"""Companies module — public API surface.

Import from here to depend on the companies module without coupling to
internal paths (``services/``, ``repositories/``, ``dependencies/``).
"""

from modules.companies.dependencies import get_current_company
from modules.companies.services.company_service import CompanyService

__all__ = [
    "CompanyService",
    "get_current_company",
]
