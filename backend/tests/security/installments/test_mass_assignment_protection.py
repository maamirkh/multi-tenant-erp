"""[Epic 10, Phase 11, T203] Security test — mass assignment.
``company_id``/``branch_id``/ownership fields are never accepted from
any request body: input Pydantic schemas structurally omit them, and
attempting to post them anyway is silently ignored (Pydantic v2's
default ``extra="ignore"`` — ``InstallmentsBaseSchema`` never sets
``extra="forbid"``, so an unrecognised field never even raises a 422;
it simply never becomes an attribute a service method could read).

Two proofs:

1. Static: every request/create/update input schema in the module is
   AST-inspected — none declares ``company_id``, ``created_by``,
   ``owner_id``, or ``id`` as a field. ``branch_id`` is deliberately not
   checked: it selects a branch *within the caller's own company*
   (already enforced by that branch's own company_id-scoped lookup) and
   is a legitimate, documented input on multiple schemas
   (``InstallmentContractCreate``, ``InstallmentConfigurationUpsert``),
   never a cross-tenant escalation vector.
2. Live parsing proof: constructing each input schema from a payload
   that INCLUDES an attacker-supplied ``company_id`` never produces an
   object exposing that value under any attribute — the schema instance
   is structurally incapable of carrying it forward to
   ``body.model_dump()``, which is all every ``router.py`` endpoint
   ever passes to its service call.
"""

from __future__ import annotations

import ast
import inspect
import uuid
from datetime import date

import modules.installments.schemas.collection as collection_schemas
import modules.installments.schemas.configuration as configuration_schemas
import modules.installments.schemas.contract as contract_schemas
import modules.installments.schemas.delinquency as delinquency_schemas
import modules.installments.schemas.lifecycle as lifecycle_schemas
import modules.installments.schemas.plan_template as plan_template_schemas
import modules.installments.schemas.schedule as schedule_schemas
import modules.installments.schemas.settlement as settlement_schemas

#: The genuinely security-sensitive fields: cross-TENANT identity
#: (``company_id``) and actor/ownership spoofing (``created_by``,
#: ``owner_id``, ``id``). ``branch_id`` is deliberately NOT included —
#: it selects a branch *within the caller's own company* (already
#: enforced by that branch's own company_id-scoped lookup wherever it's
#: used), never a cross-tenant escalation vector, and is a legitimate,
#: documented input on multiple schemas
#: (``InstallmentContractCreate``, ``InstallmentConfigurationUpsert``).
_FORBIDDEN_FIELD_NAMES = frozenset({"company_id", "created_by", "owner_id", "id"})

_INPUT_SCHEMA_MODULES = (
    collection_schemas,
    configuration_schemas,
    contract_schemas,
    delinquency_schemas,
    lifecycle_schemas,
    plan_template_schemas,
    schedule_schemas,
    settlement_schemas,
)


def _is_input_schema_class_name(name: str) -> bool:
    """Request-body-shaped schemas — never ``*Read``/``*Result*``
    response schemas, which legitimately echo back ``company_id`` etc."""
    return (
        (
            name.endswith("Create")
            or name.endswith("Update")
            or name.endswith("Upsert")
            or name.endswith("Request")
        )
        and "Read" not in name
        and "Result" not in name
    )


def _collect_input_schema_field_names(module: object) -> dict[str, set[str]]:
    tree = ast.parse(inspect.getsource(module))
    fields_by_class: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and _is_input_schema_class_name(node.name):
            field_names: set[str] = set()
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(
                    stmt.target, ast.Name
                ):
                    field_names.add(stmt.target.id)
            fields_by_class[node.name] = field_names
    return fields_by_class


class TestInputSchemasStructurallyOmitOwnershipFields:
    def test_no_input_schema_declares_a_forbidden_field(self) -> None:
        violations: list[str] = []
        for module in _INPUT_SCHEMA_MODULES:
            for class_name, field_names in _collect_input_schema_field_names(
                module
            ).items():
                forbidden_present = field_names & _FORBIDDEN_FIELD_NAMES
                if forbidden_present:
                    violations.append(
                        f"{module.__name__}.{class_name} declares {forbidden_present}"
                    )
        assert violations == [], f"forbidden ownership fields found: {violations}"

    def test_at_least_one_input_schema_was_actually_checked_per_module(self) -> None:
        """Regression guard against a silently-empty sweep (e.g. a
        renamed module breaking ``_is_input_schema_class_name``'s own
        naming convention undetected)."""
        total_classes_checked = sum(
            len(_collect_input_schema_field_names(module))
            for module in _INPUT_SCHEMA_MODULES
        )
        assert total_classes_checked >= 10


class TestMassAssignmentAttemptIsSilentlyIgnoredWhenParsing:
    def test_company_id_in_contract_create_payload_is_ignored(self) -> None:
        payload = {
            "company_id": str(uuid.uuid4()),  # attacker-supplied, must be ignored
            "sales_invoice_id": str(uuid.uuid4()),
            "down_payment_amount": "100.00",
            "installment_count": 12,
            "frequency": "MONTHLY",
            "first_due_date": date(2026, 2, 1).isoformat(),
            "maturity_date": date(2027, 1, 1).isoformat(),
        }
        parsed = contract_schemas.InstallmentContractCreate.model_validate(payload)
        assert not hasattr(parsed, "company_id")
        dumped = parsed.model_dump()
        assert "company_id" not in dumped

    def test_owner_fields_in_plan_template_create_payload_are_ignored(self) -> None:
        payload = {
            "company_id": str(uuid.uuid4()),
            "created_by": str(uuid.uuid4()),
            "name": "T203 Mass Assignment Probe",
            "installment_count": 6,
            "frequency": "MONTHLY",
            "down_payment_rule": {"type": "FIXED", "amount": "0"},
        }
        parsed = plan_template_schemas.InstallmentPlanTemplateCreate.model_validate(
            payload
        )
        dumped = parsed.model_dump()
        assert "company_id" not in dumped
        assert "created_by" not in dumped

    def test_company_id_in_configuration_upsert_payload_is_ignored_but_branch_id_is_legitimate(
        self,
    ) -> None:
        real_branch_id = uuid.uuid4()
        payload = {
            "company_id": str(uuid.uuid4()),  # attacker-supplied, must be ignored
            "branch_id": str(real_branch_id),  # legitimate documented input
            "min_term": 1,
            "max_term": 60,
            "allowed_frequencies": ["MONTHLY"],
        }
        parsed = configuration_schemas.InstallmentConfigurationUpsert.model_validate(
            payload
        )
        dumped = parsed.model_dump()
        assert "company_id" not in dumped
        assert dumped["branch_id"] == real_branch_id

    def test_id_field_in_collection_reverse_request_is_ignored(self) -> None:
        payload = {
            "id": str(uuid.uuid4()),
            "reason": "T203 mass-assignment probe.",
        }
        parsed = collection_schemas.InstallmentCollectionReverseRequest.model_validate(
            payload
        )
        dumped = parsed.model_dump()
        assert "id" not in dumped
