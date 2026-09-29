"""Every drill-down ``target_route`` must be a real frontend page
(FR-RPT-180).

The routes are UI paths, not API paths: a route with no matching
``page.tsx`` under ``frontend/src/app`` renders a 404 when a user clicks
it. Route groups ``(name)`` add no URL segment; a ``{field}`` placeholder
matches a dynamic ``[param]`` segment. Dashboard widget routes
(``/analytics/<key>``) must also name a registered report.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import modules.reports.registry.load_all  # noqa: F401 — populates the registry
from modules.reports.registry.definitions import REPORT_REGISTRY

_APP_DIR = Path(__file__).resolve().parents[5] / "frontend" / "src" / "app"
_DASHBOARD_SERVICE = (
    Path(__file__).resolve().parents[4]
    / "modules"
    / "reports"
    / "services"
    / "dashboard_service.py"
)


def _ui_routes() -> set[tuple[str, ...]]:
    routes: set[tuple[str, ...]] = set()
    for page in _APP_DIR.rglob("page.tsx"):
        parts = page.relative_to(_APP_DIR).parts[:-1]
        segments = tuple(
            "[]" if p.startswith("[") else p
            for p in parts
            if not (p.startswith("(") and p.endswith(")"))
        )
        routes.add(segments)
    return routes


def _segments(route: str) -> tuple[str, ...]:
    path = route.split("?", 1)[0]
    return tuple(
        "[]" if re.fullmatch(r"\{\w+\}", s) else s for s in path.strip("/").split("/")
    )


def _matches(route: tuple[str, ...], page: tuple[str, ...]) -> bool:
    """A literal segment also matches a dynamic ``[param]`` page segment."""
    return len(route) == len(page) and all(
        r == p or p == "[]" for r, p in zip(route, page, strict=True)
    )


def _all_targets() -> list[tuple[str, str]]:
    targets = [
        (key, target.target_route)
        for key, definition in REPORT_REGISTRY.items()
        for target in definition.drill_down_targets
    ]
    source = _DASHBOARD_SERVICE.read_text(encoding="utf-8")
    targets += [
        ("exec.dashboard", route)
        for route in re.findall(r'target_route="([^"]+)"', source)
    ]
    return targets


@pytest.mark.skipif(not _APP_DIR.is_dir(), reason="frontend sources not present")
def test_every_drill_down_route_is_a_frontend_page() -> None:
    routes = _ui_routes()
    missing = [
        f"{key}: {route}"
        for key, route in _all_targets()
        if not any(_matches(_segments(route), page) for page in routes)
    ]
    assert missing == []


def test_dashboard_drill_downs_name_registered_reports() -> None:
    for _, route in _all_targets():
        if route.startswith("/analytics/"):
            report_key = route.split("?", 1)[0].removeprefix("/analytics/")
            assert report_key in REPORT_REGISTRY, route
