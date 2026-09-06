"""Chart of Accounts industry templates — Phase 2 seed data.

Provides 6 industry COA templates per tasks.md T056: Retail, Manufacturing,
Services, Construction, Medical, and Generic. Each template is built from a
shared "core" set of accounts/groups (common to every business — cash,
bank, AR/AP, standard equity and overhead accounts) plus industry-specific
additions, avoiding repetition across templates (DRY).

Account groups follow spec.md §13.3; account codes follow the standard
ranges in spec.md §13.5 (1000s Assets, 2000s Liabilities, 3000s Equity,
4000s Revenue, 5000s COGS, 6000s-8000s Opex, 9000s reserved).

Spec ref: specs/008-accounting-finance/spec.md §13.8 COA Templates
Task ref: specs/008-accounting-finance/tasks.md T056
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from modules.accounting.constants import AccountType


@dataclass(frozen=True)
class GroupDef:
    group_code: str
    group_name: str
    account_type: str
    display_order: int = 0


@dataclass(frozen=True)
class AccountDef:
    account_code: str
    account_name: str
    account_type: str
    group_code: str
    is_leaf: bool = True
    is_bank_account: bool = False
    is_cash_account: bool = False
    requires_cost_center: bool = False


@dataclass(frozen=True)
class COATemplate:
    key: str
    label: str
    groups: tuple[GroupDef, ...]
    accounts: tuple[AccountDef, ...]


# ---------------------------------------------------------------------------
# Shared groups (spec.md §13.3)
# ---------------------------------------------------------------------------

_CORE_GROUPS: Final[tuple[GroupDef, ...]] = (
    GroupDef("CUR-AST", "Current Assets", AccountType.ASSET.value, 1),
    GroupDef("FIX-AST", "Fixed Assets", AccountType.ASSET.value, 2),
    GroupDef("INT-AST", "Intangible Assets", AccountType.ASSET.value, 3),
    GroupDef("OTH-AST", "Other Assets", AccountType.ASSET.value, 4),
    GroupDef("CUR-LIA", "Current Liabilities", AccountType.LIABILITY.value, 1),
    GroupDef("LT-LIA", "Long-Term Liabilities", AccountType.LIABILITY.value, 2),
    GroupDef("OTH-LIA", "Other Liabilities", AccountType.LIABILITY.value, 3),
    GroupDef("SHR-CAP", "Share Capital", AccountType.EQUITY.value, 1),
    GroupDef("RET-EAR", "Retained Earnings", AccountType.EQUITY.value, 2),
    GroupDef("OTH-EQ", "Other Equity", AccountType.EQUITY.value, 3),
    GroupDef("OP-REV", "Operating Revenue", AccountType.REVENUE.value, 1),
    GroupDef("OTH-INC", "Other Income", AccountType.REVENUE.value, 2),
    GroupDef("EXC-ITM", "Exceptional Items", AccountType.REVENUE.value, 3),
    GroupDef("COGS", "Cost of Goods Sold", AccountType.EXPENSE.value, 1),
    GroupDef("OP-EXP", "Operating Expenses", AccountType.EXPENSE.value, 2),
    GroupDef("FIN-EXP", "Financial Expenses", AccountType.EXPENSE.value, 3),
    GroupDef("EXC-EXP", "Exceptional Expenses", AccountType.EXPENSE.value, 4),
)

# ---------------------------------------------------------------------------
# Core accounts — common to every industry
# ---------------------------------------------------------------------------

_CORE_ACCOUNTS: Final[tuple[AccountDef, ...]] = (
    AccountDef(
        "1000", "Cash on Hand", AccountType.ASSET.value, "CUR-AST", is_cash_account=True
    ),
    AccountDef(
        "1010",
        "Main Bank Account",
        AccountType.ASSET.value,
        "CUR-AST",
        is_bank_account=True,
    ),
    AccountDef("1100", "Accounts Receivable", AccountType.ASSET.value, "CUR-AST"),
    AccountDef(
        "1150", "Allowance for Doubtful Accounts", AccountType.ASSET.value, "CUR-AST"
    ),
    AccountDef("1200", "Prepaid Expenses", AccountType.ASSET.value, "CUR-AST"),
    AccountDef("1400", "Input Tax Recoverable", AccountType.ASSET.value, "CUR-AST"),
    AccountDef("1500", "Furniture & Fixtures", AccountType.ASSET.value, "FIX-AST"),
    AccountDef("1510", "Office Equipment", AccountType.ASSET.value, "FIX-AST"),
    AccountDef("1590", "Accumulated Depreciation", AccountType.ASSET.value, "FIX-AST"),
    AccountDef("1700", "Goodwill", AccountType.ASSET.value, "INT-AST"),
    AccountDef("1900", "Other Non-Current Assets", AccountType.ASSET.value, "OTH-AST"),
    AccountDef("2000", "Accounts Payable", AccountType.LIABILITY.value, "CUR-LIA"),
    AccountDef("2100", "Accrued Expenses", AccountType.LIABILITY.value, "CUR-LIA"),
    AccountDef("2200", "Output Tax Payable", AccountType.LIABILITY.value, "CUR-LIA"),
    AccountDef(
        "2300", "Withholding Tax Payable", AccountType.LIABILITY.value, "CUR-LIA"
    ),
    AccountDef(
        "2500", "Long-Term Loans Payable", AccountType.LIABILITY.value, "LT-LIA"
    ),
    AccountDef("2900", "Other Liabilities", AccountType.LIABILITY.value, "OTH-LIA"),
    AccountDef("3000", "Share Capital", AccountType.EQUITY.value, "SHR-CAP"),
    AccountDef("3500", "Retained Earnings", AccountType.EQUITY.value, "RET-EAR"),
    AccountDef("3900", "Other Equity Reserves", AccountType.EQUITY.value, "OTH-EQ"),
    AccountDef("4000", "Sales Revenue", AccountType.REVENUE.value, "OP-REV"),
    AccountDef("4900", "Other Income", AccountType.REVENUE.value, "OTH-INC"),
    AccountDef("4950", "Foreign Exchange Gain", AccountType.REVENUE.value, "OTH-INC"),
    AccountDef("4990", "Exceptional Income", AccountType.REVENUE.value, "EXC-ITM"),
    AccountDef("6000", "Salaries & Wages", AccountType.EXPENSE.value, "OP-EXP"),
    AccountDef("6100", "Rent Expense", AccountType.EXPENSE.value, "OP-EXP"),
    AccountDef("6200", "Utilities Expense", AccountType.EXPENSE.value, "OP-EXP"),
    AccountDef("6300", "Office Supplies Expense", AccountType.EXPENSE.value, "OP-EXP"),
    AccountDef("6400", "Depreciation Expense", AccountType.EXPENSE.value, "OP-EXP"),
    AccountDef("6500", "Bad Debt Expense", AccountType.EXPENSE.value, "OP-EXP"),
    AccountDef("8000", "Bank Charges", AccountType.EXPENSE.value, "FIN-EXP"),
    AccountDef("8100", "Interest Expense", AccountType.EXPENSE.value, "FIN-EXP"),
    AccountDef("8200", "Foreign Exchange Loss", AccountType.EXPENSE.value, "FIN-EXP"),
    AccountDef("8900", "Exceptional Expenses", AccountType.EXPENSE.value, "EXC-EXP"),
)


def _template(
    key: str, label: str, extra_accounts: tuple[AccountDef, ...]
) -> COATemplate:
    return COATemplate(
        key=key,
        label=label,
        groups=_CORE_GROUPS,
        accounts=_CORE_ACCOUNTS + extra_accounts,
    )


# ---------------------------------------------------------------------------
# Industry-specific extensions
# ---------------------------------------------------------------------------

_RETAIL_EXTRA: Final[tuple[AccountDef, ...]] = (
    AccountDef("1300", "Merchandise Inventory", AccountType.ASSET.value, "CUR-AST"),
    AccountDef("5000", "Cost of Goods Sold", AccountType.EXPENSE.value, "COGS"),
    AccountDef("5100", "Purchase Discounts", AccountType.EXPENSE.value, "COGS"),
    AccountDef("5200", "Inventory Shrinkage", AccountType.EXPENSE.value, "COGS"),
    AccountDef("6600", "Store Supplies Expense", AccountType.EXPENSE.value, "OP-EXP"),
    AccountDef("6700", "Point-of-Sale Fees", AccountType.EXPENSE.value, "OP-EXP"),
)

_MANUFACTURING_EXTRA: Final[tuple[AccountDef, ...]] = (
    AccountDef("1310", "Raw Materials Inventory", AccountType.ASSET.value, "CUR-AST"),
    AccountDef(
        "1320", "Work-in-Progress Inventory", AccountType.ASSET.value, "CUR-AST"
    ),
    AccountDef("1330", "Finished Goods Inventory", AccountType.ASSET.value, "CUR-AST"),
    AccountDef("1520", "Plant & Machinery", AccountType.ASSET.value, "FIX-AST"),
    AccountDef("5000", "Cost of Goods Manufactured", AccountType.EXPENSE.value, "COGS"),
    AccountDef("5010", "Direct Materials Consumed", AccountType.EXPENSE.value, "COGS"),
    AccountDef("5020", "Direct Labor", AccountType.EXPENSE.value, "COGS"),
    AccountDef("5030", "Manufacturing Overhead", AccountType.EXPENSE.value, "COGS"),
    AccountDef("5040", "Factory Depreciation", AccountType.EXPENSE.value, "COGS"),
    AccountDef("6600", "Machinery Maintenance", AccountType.EXPENSE.value, "OP-EXP"),
)

_SERVICES_EXTRA: Final[tuple[AccountDef, ...]] = (
    AccountDef(
        "4100", "Professional Fees Revenue", AccountType.REVENUE.value, "OP-REV"
    ),
    AccountDef("4200", "Retainer Revenue", AccountType.REVENUE.value, "OP-REV"),
    AccountDef("5000", "Subcontractor Costs", AccountType.EXPENSE.value, "COGS"),
    AccountDef("6600", "Professional Development", AccountType.EXPENSE.value, "OP-EXP"),
    AccountDef(
        "6700", "Travel & Client Entertainment", AccountType.EXPENSE.value, "OP-EXP"
    ),
)

_CONSTRUCTION_EXTRA: Final[tuple[AccountDef, ...]] = (
    AccountDef(
        "1340", "Construction Materials Inventory", AccountType.ASSET.value, "CUR-AST"
    ),
    AccountDef(
        "1350", "Contracts in Progress (WIP)", AccountType.ASSET.value, "CUR-AST"
    ),
    AccountDef("1530", "Heavy Equipment", AccountType.ASSET.value, "FIX-AST"),
    AccountDef("2150", "Retention Payable", AccountType.LIABILITY.value, "CUR-LIA"),
    AccountDef("4300", "Contract Revenue", AccountType.REVENUE.value, "OP-REV"),
    AccountDef("5000", "Direct Construction Costs", AccountType.EXPENSE.value, "COGS"),
    AccountDef("5050", "Subcontractor Costs", AccountType.EXPENSE.value, "COGS"),
    AccountDef("5060", "Equipment Rental", AccountType.EXPENSE.value, "COGS"),
    AccountDef("6600", "Site Safety & Compliance", AccountType.EXPENSE.value, "OP-EXP"),
)

_MEDICAL_EXTRA: Final[tuple[AccountDef, ...]] = (
    AccountDef("1120", "Patient Receivables", AccountType.ASSET.value, "CUR-AST"),
    AccountDef(
        "1130", "Insurance Claims Receivable", AccountType.ASSET.value, "CUR-AST"
    ),
    AccountDef(
        "1360", "Medical Supplies Inventory", AccountType.ASSET.value, "CUR-AST"
    ),
    AccountDef("1540", "Medical Equipment", AccountType.ASSET.value, "FIX-AST"),
    AccountDef("4400", "Patient Service Revenue", AccountType.REVENUE.value, "OP-REV"),
    AccountDef(
        "4410", "Insurance Reimbursement Revenue", AccountType.REVENUE.value, "OP-REV"
    ),
    AccountDef("5000", "Medical Supplies Consumed", AccountType.EXPENSE.value, "COGS"),
    AccountDef("6600", "Clinical Staff Wages", AccountType.EXPENSE.value, "OP-EXP"),
    AccountDef(
        "6700", "Medical Licensing & Compliance", AccountType.EXPENSE.value, "OP-EXP"
    ),
)

_GENERIC_EXTRA: Final[tuple[AccountDef, ...]] = (
    AccountDef("1300", "Inventory", AccountType.ASSET.value, "CUR-AST"),
    AccountDef("5000", "Cost of Goods Sold", AccountType.EXPENSE.value, "COGS"),
)


COA_TEMPLATES: Final[dict[str, COATemplate]] = {
    t.key: t
    for t in (
        _template("RETAIL", "Retail", _RETAIL_EXTRA),
        _template("MANUFACTURING", "Manufacturing", _MANUFACTURING_EXTRA),
        _template("SERVICES", "Services / Professional Services", _SERVICES_EXTRA),
        _template("CONSTRUCTION", "Construction", _CONSTRUCTION_EXTRA),
        _template("MEDICAL", "Medical / Healthcare", _MEDICAL_EXTRA),
        _template("GENERIC", "Generic", _GENERIC_EXTRA),
    )
}


def list_template_keys() -> list[str]:
    """Return all available template keys, e.g. for a frontend dropdown."""
    return list(COA_TEMPLATES.keys())


def get_template(key: str) -> COATemplate:
    """Return the named template.

    Raises:
        ValueError: If ``key`` is not a recognised template.
    """
    template = COA_TEMPLATES.get(key.upper())
    if template is None:
        raise ValueError(
            f"Unknown COA template: '{key}'. Valid templates: {list_template_keys()}"
        )
    return template
