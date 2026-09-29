"""T271 (FR-RPT-223) — every group-by-capable ``ReportDefinition`` (a NOW
entry with at least one ``supported_dimensions`` value) documents its
practical grouping-cardinality ceiling in a one-line
``# group-by cardinality:`` comment directly above its ``key=`` line.
Grep-based presence test: a new group-by report cannot land without one.
"""

from __future__ import annotations

import pathlib
import re

import modules.reports.registry as registry_pkg
import modules.reports.registry.load_all  # noqa: F401 — full catalog
from modules.reports.registry.definitions import REPORT_REGISTRY, ReportStatus

_MARKER = "# group-by cardinality:"


def _catalog_lines() -> list[str]:
    root = pathlib.Path(registry_pkg.__file__).parent
    lines: list[str] = []
    for path in sorted(root.glob("catalog_*.py")):
        lines.extend(path.read_text(encoding="utf-8").splitlines())
    return lines


def test_every_group_by_report_documents_its_cardinality_ceiling() -> None:
    lines = _catalog_lines()
    group_by_keys = sorted(
        d.key
        for d in REPORT_REGISTRY.values()
        if d.status is ReportStatus.NOW and d.supported_dimensions
    )
    assert group_by_keys, "expected group-by-capable reports in the catalog"

    missing: list[str] = []
    for key in group_by_keys:
        pattern = re.compile(rf'^\s*key="{re.escape(key)}",\s*$')
        index = next((i for i, line in enumerate(lines) if pattern.match(line)), None)
        if index is None or index == 0:
            missing.append(f"{key}: no literal key= line")
            continue
        comment = lines[index - 1].strip()
        if not comment.startswith(_MARKER) or len(comment) <= len(_MARKER) + 3:
            missing.append(key)
    assert missing == [], f"undocumented group-by cardinality: {missing}"


def test_every_documented_ceiling_says_how_it_is_bounded() -> None:
    """Each ceiling names its bound — a pagination style, a fixed/capped
    set, or exactly one — never an open-ended 'many'."""
    bounded_by = ("paged", "one statement", "one aggregate", "exactly one", "capped")
    comments = [line.strip() for line in _catalog_lines() if _MARKER in line]
    assert comments
    for comment in comments:
        assert any(word in comment for word in bounded_by), comment
