"""CSV formula-injection protection (spec §30, FR-RPT-210 export security).

Excel/Sheets/Numbers treat a cell beginning with ``=``, ``+``, ``-``, or
``@`` as a formula. A malicious value in exported report data (e.g. a
customer name) could otherwise execute arbitrary formulas/macros when the
export is opened. Every exported cell is sanitized before being written.
"""

from __future__ import annotations

_FORMULA_PREFIXES = ("=", "+", "-", "@")


def sanitize_cell(value: str) -> str:
    """Neutralize a formula-injection-capable prefix by prepending a
    single-quote escape character — the standard CSV-formula-injection
    mitigation (OWASP CSV Injection). Non-string-shaped values are
    returned unmodified by the caller (this function only ever receives
    already-stringified cell values)."""
    if value.startswith(_FORMULA_PREFIXES):
        return f"'{value}"
    return value
