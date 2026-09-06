"""[T177] Contract conformance test against
`specs/009a-platform-admin/contracts/platform-admin-v1.yaml` — Epic 9A
Phase 13.

Every declared path exists with the declared method and permission; no
undeclared CRUD was invented (an endpoint present in code but absent
from the contract also fails). Reads the real YAML contract file
directly (the source of truth) rather than a hand-duplicated Python
copy that could itself silently drift from it.

**Path resolution note**: this test walks up from its own file location
to find `specs/009a-platform-admin/contracts/platform-admin-v1.yaml` at
the repo root. The `erp-system-api-1` Docker container only bind-mounts
`./backend:/app` — `specs/` is not visible inside it — so this specific
test file must be run via the local venv (full repo checkout), not
inside the container. It needs no database and no `test_client`/
`db_session` fixture at all: it is a pure static check against the
FastAPI app's route table and the YAML contract, so it also runs fast
and portably wherever the full repo is checked out.

**Permission introspection**: `require_platform_permission()`
(`dependencies.py`) tags its returned dependency callable with a
`permission_code` attribute specifically so this test can verify the
*wired* permission without a second, hand-maintained mapping.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi.routing import APIRoute, APIRouter

from main import create_app

_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _contract_path() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = (
            parent
            / "specs"
            / "009a-platform-admin"
            / "contracts"
            / "platform-admin-v1.yaml"
        )
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "platform-admin-v1.yaml not found by walking up from "
        f"{here} — this test must be run against a full repo checkout, "
        "not inside a container that only mounts backend/."
    )


def _load_contract_spec() -> dict[str, Any]:
    with _contract_path().open() as f:
        spec: dict[str, Any] = yaml.safe_load(f)
        return spec


def _load_contract_operations() -> dict[tuple[str, str], str | None]:
    """`{(METHOD, full_path): x-permission or None}` for every declared
    operation, with the server prefix (`/api/v1/platform`) prepended."""
    spec = _load_contract_spec()
    server_prefix = spec["servers"][0]["url"]
    operations: dict[tuple[str, str], str | None] = {}
    for path, methods in spec["paths"].items():
        full_path = server_prefix + path
        for method, operation in methods.items():
            if method not in _HTTP_METHODS:
                continue
            operations[(method.upper(), full_path)] = operation.get("x-permission")
    return operations


def _flatten_app_routes(
    router: APIRouter, prefix: str = ""
) -> list[tuple[str, APIRoute]]:
    """Recursively resolve full mounted paths — this FastAPI version
    wraps every `include_router()` call in an `_IncludedRouter` that
    carries its own prefix in `include_context.prefix`, rather than
    flattening prefixes into `route.path` eagerly."""
    routes: list[tuple[str, APIRoute]] = []
    for r in router.routes:
        original_router: APIRouter | None = getattr(r, "original_router", None)
        if original_router is not None:
            include_context = getattr(r, "include_context", None)
            sub_prefix = prefix + (getattr(include_context, "prefix", "") or "")
            routes.extend(_flatten_app_routes(original_router, sub_prefix))
        elif isinstance(r, APIRoute):
            routes.append((prefix + r.path, r))
    return routes


def _load_actual_platform_operations() -> dict[tuple[str, str], set[str]]:
    """`{(METHOD, full_path): {wired permission_code, ...}}` for every
    mounted `/api/v1/platform/*` route."""
    app = create_app()
    flattened = _flatten_app_routes(app.router)
    operations: dict[tuple[str, str], set[str]] = {}
    for path, route in flattened:
        if not path.startswith("/api/v1/platform"):
            continue
        codes: set[str] = {
            code
            for dep in route.dependant.dependencies
            if (code := getattr(dep.call, "permission_code", None)) is not None
        }
        for method in route.methods or set():
            if method in ("HEAD", "OPTIONS"):
                continue
            operations[(method, path)] = codes
    return operations


class TestContractConformance:
    def test_contract_declares_exactly_28_paths_and_33_operations(self) -> None:
        spec = _load_contract_spec()
        paths = spec["paths"]
        assert len(paths) == 28, f"expected 28 paths, found {len(paths)}"
        total_operations = sum(
            1 for methods in paths.values() for m in methods if m in _HTTP_METHODS
        )
        assert total_operations == 33, (
            f"expected 33 operations, found {total_operations}"
        )

    def test_every_contract_operation_is_implemented_with_matching_permission(
        self,
    ) -> None:
        contract_ops = _load_contract_operations()
        actual_ops = _load_actual_platform_operations()

        missing: list[tuple[str, str]] = []
        wrong_permission: list[tuple[str, str, str | None, set[str]]] = []

        for (method, path), expected_permission in contract_ops.items():
            if (method, path) not in actual_ops:
                missing.append((method, path))
                continue
            actual_codes = actual_ops[(method, path)]
            if expected_permission is None:
                if actual_codes:
                    wrong_permission.append(
                        (method, path, expected_permission, actual_codes)
                    )
            elif expected_permission not in actual_codes:
                wrong_permission.append(
                    (method, path, expected_permission, actual_codes)
                )

        assert missing == [], f"Declared-but-missing operations: {missing}"
        assert wrong_permission == [], (
            f"Permission mismatches (method, path, expected, actual): "
            f"{wrong_permission}"
        )

    def test_no_undeclared_platform_route_exists(self) -> None:
        contract_ops = _load_contract_operations()
        actual_ops = _load_actual_platform_operations()

        undeclared = sorted(k for k in actual_ops if k not in contract_ops)
        assert undeclared == [], (
            f"Implemented-but-undeclared routes (not in contract): {undeclared}"
        )
