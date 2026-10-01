"""T147 — Metric catalog distinct-name discipline (FR-RPT-020/021, SC-004).

No two ``MetricDefinition``s share a ``label`` while having a different
``authoritative_domain``/``source_call`` — the "same name, two meanings"
drift the governing prompt explicitly warns against (spec §10).
``metric.sales.line_margin`` vs. ``metric.accounting.gross_profit_margin``
must be explicitly distinct.
"""

from __future__ import annotations

from modules.reports.metrics.definitions import METRIC_CATALOG


def test_exactly_sixteen_entries() -> None:
    assert len(METRIC_CATALOG) == 16


def test_semantic_ids_match_their_dict_key() -> None:
    for key, definition in METRIC_CATALOG.items():
        assert definition.semantic_id == key


def test_no_two_labels_share_a_different_definition() -> None:
    by_label: dict[str, set[tuple[str, str]]] = {}
    for definition in METRIC_CATALOG.values():
        by_label.setdefault(definition.label, set()).add(
            (definition.authoritative_domain.value, definition.source_call)
        )
    for label, definitions in by_label.items():
        assert len(definitions) == 1, (
            f"Label '{label}' is shared by distinct definitions: {definitions}"
        )


def test_line_margin_and_gross_profit_margin_are_explicitly_distinct() -> None:
    line_margin = METRIC_CATALOG["metric.sales.line_margin"]
    gross_profit_margin = METRIC_CATALOG["metric.accounting.gross_profit_margin"]

    assert line_margin.label != gross_profit_margin.label
    assert line_margin.authoritative_domain != gross_profit_margin.authoritative_domain
    assert line_margin.source_call != gross_profit_margin.source_call
