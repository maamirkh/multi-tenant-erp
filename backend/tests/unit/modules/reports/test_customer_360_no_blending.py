"""T173 (FR-RPT-113) — no field in ``schemas/customer_360.py`` sums or
blends two domains' figures. Structural check: ``Customer360Response``'s
own top level carries only identity + the four independent sections
(never an extra combined/summary field spanning them), and each
``Present*Section``'s field set stays within its own domain vocabulary.
"""

from __future__ import annotations

from modules.reports.schemas.customer_360 import (
    Customer360Response,
    PresentAccountingArSection,
    PresentCrmSection,
    PresentInstallmentsSection,
    PresentSalesSection,
)

_BLENDING_KEYWORDS = (
    "combined",
    "blended",
    "total_exposure",
    "grand_total",
    "aggregate",
)


def test_customer_360_response_has_no_extra_summary_field() -> None:
    assert set(Customer360Response.model_fields) == {
        "customer_id",
        "customer_name",
        "sales",
        "accounting_ar",
        "crm",
        "installments",
    }


def test_no_present_section_field_name_suggests_cross_domain_blending() -> None:
    for section_model in (
        PresentSalesSection,
        PresentAccountingArSection,
        PresentCrmSection,
        PresentInstallmentsSection,
    ):
        for field_name in section_model.model_fields:
            lowered = field_name.lower()
            assert not any(keyword in lowered for keyword in _BLENDING_KEYWORDS), (
                f"{section_model.__name__}.{field_name} looks like a blended figure"
            )


def test_no_two_present_sections_share_a_field_name() -> None:
    """Each section's fields are domain-specific — no shared field name
    that could later be silently summed across sections by a consumer."""
    field_sets = [
        set(PresentSalesSection.model_fields) - {"state"},
        set(PresentAccountingArSection.model_fields) - {"state"},
        set(PresentCrmSection.model_fields) - {"state"},
        set(PresentInstallmentsSection.model_fields) - {"state"},
    ]
    all_fields = [name for fields in field_sets for name in fields]
    assert len(all_fields) == len(set(all_fields))
