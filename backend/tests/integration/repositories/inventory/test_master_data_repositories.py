"""Integration tests for master data repositories: Brand, UOM, Tag, ReasonCode,
CustomField, AttributeDefinition, AttributeSet.

Tests: CRUD operations, company_id scoping, soft-delete, code uniqueness.

Task: T050
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from modules.inventory.models.attribute import (
    AttributeDefinition,
    AttributeSet,
    AttributeSetMembership,
)
from modules.inventory.models.brand import Brand
from modules.inventory.models.custom_field import CustomFieldDefinition
from modules.inventory.models.reason_code import ReasonCode
from modules.inventory.models.tag import Tag
from modules.inventory.models.uom import UOM, UOMConversion
from modules.inventory.repositories.attribute_repository import (
    AttributeDefinitionRepository,
    AttributeSetMembershipRepository,
    AttributeSetRepository,
)
from modules.inventory.repositories.brand_repository import BrandRepository
from modules.inventory.repositories.custom_field_repository import (
    CustomFieldDefinitionRepository,
)
from modules.inventory.repositories.reason_code_repository import ReasonCodeRepository
from modules.inventory.repositories.tag_repository import TagRepository
from modules.inventory.repositories.uom_repository import (
    UOMConversionRepository,
    UOMRepository,
)

# =============================================================================
# BrandRepository
# =============================================================================


class TestBrandRepository:
    def test_create_and_get_by_id(self, db_session: Session) -> None:
        repo = BrandRepository(db_session)
        cid = uuid.uuid4()
        brand = Brand(company_id=cid, code="SONY", name="Sony", status="active")
        created = repo.create(brand)
        assert created.id is not None
        found = repo.get_by_id(id=created.id, company_id=cid)
        assert found.code == "SONY"

    def test_get_by_code_returns_none_when_not_found(self, db_session: Session) -> None:
        repo = BrandRepository(db_session)
        result = repo.get_by_code(company_id=uuid.uuid4(), code="NOTHERE")
        assert result is None

    def test_get_by_code_isolates_by_company(self, db_session: Session) -> None:
        repo = BrandRepository(db_session)
        cid_a, cid_b = uuid.uuid4(), uuid.uuid4()
        repo.create(
            Brand(company_id=cid_a, code="BRAND", name="Brand A", status="active")
        )
        repo.create(
            Brand(company_id=cid_b, code="BRAND", name="Brand B", status="active")
        )
        a = repo.get_by_code(company_id=cid_a, code="BRAND")
        b = repo.get_by_code(company_id=cid_b, code="BRAND")
        assert a is not None and b is not None
        assert a.id != b.id

    def test_list_active_excludes_inactive(self, db_session: Session) -> None:
        repo = BrandRepository(db_session)
        cid = uuid.uuid4()
        repo.create(
            Brand(company_id=cid, code="A", name="Active Brand", status="active")
        )
        repo.create(
            Brand(company_id=cid, code="B", name="Inactive Brand", status="inactive")
        )
        active = repo.list_active(company_id=cid)
        assert all(b.status == "active" for b in active)
        assert len(active) == 1

    def test_soft_delete_hides_from_get_by_code(self, db_session: Session) -> None:
        repo = BrandRepository(db_session)
        cid = uuid.uuid4()
        brand = repo.create(
            Brand(company_id=cid, code="DEL", name="To Delete", status="active")
        )
        repo.soft_delete(id=brand.id, company_id=cid)
        result = repo.get_by_code(company_id=cid, code="DEL")
        assert result is None

    def test_tenant_isolation_for_get_by_id(self, db_session: Session) -> None:
        repo = BrandRepository(db_session)
        cid = uuid.uuid4()
        brand = repo.create(Brand(company_id=cid, code="X", name="X", status="active"))
        from core.exceptions.base import NotFoundException

        with pytest.raises(NotFoundException):
            repo.get_by_id(id=brand.id, company_id=uuid.uuid4())


# =============================================================================
# UOMRepository
# =============================================================================


class TestUOMRepository:
    def test_create_and_get_by_id(self, db_session: Session) -> None:
        repo = UOMRepository(db_session)
        cid = uuid.uuid4()
        uom = repo.create(
            UOM(
                company_id=cid,
                code="KG",
                name="Kilogram",
                uom_type="WEIGHT",
                status="active",
            )
        )
        assert uom.id is not None
        found = repo.get_by_id(id=uom.id, company_id=cid)
        assert found.code == "KG"

    def test_get_by_code_returns_none_when_missing(self, db_session: Session) -> None:
        repo = UOMRepository(db_session)
        assert repo.get_by_code(company_id=uuid.uuid4(), code="MISSING") is None

    def test_list_by_type_filters_correctly(self, db_session: Session) -> None:
        repo = UOMRepository(db_session)
        cid = uuid.uuid4()
        repo.create(
            UOM(
                company_id=cid, code="KG", name="KG", uom_type="WEIGHT", status="active"
            )
        )
        repo.create(
            UOM(
                company_id=cid,
                code="M",
                name="Meter",
                uom_type="LENGTH",
                status="active",
            )
        )
        weights = repo.list_by_type(company_id=cid, uom_type="WEIGHT")
        assert all(u.uom_type == "WEIGHT" for u in weights)
        assert len(weights) == 1

    def test_soft_delete_hides_from_get_by_code(self, db_session: Session) -> None:
        repo = UOMRepository(db_session)
        cid = uuid.uuid4()
        uom = repo.create(
            UOM(
                company_id=cid, code="EA", name="Each", uom_type="UNIT", status="active"
            )
        )
        repo.soft_delete(id=uom.id, company_id=cid)
        assert repo.get_by_code(company_id=cid, code="EA") is None


class TestUOMConversionRepository:
    def test_create_and_get_by_pair(self, db_session: Session) -> None:
        uom_repo = UOMRepository(db_session)
        conv_repo = UOMConversionRepository(db_session)
        cid = uuid.uuid4()
        src = uom_repo.create(
            UOM(
                company_id=cid, code="KG", name="KG", uom_type="WEIGHT", status="active"
            )
        )
        tgt = uom_repo.create(
            UOM(
                company_id=cid,
                code="G",
                name="Gram",
                uom_type="WEIGHT",
                status="active",
            )
        )
        conv = conv_repo.create(
            UOMConversion(
                company_id=cid,
                source_uom_id=str(src.id),
                target_uom_id=str(tgt.id),
                conversion_factor=1000.0,
            )
        )
        assert conv.id is not None
        found = conv_repo.get_by_pair(
            company_id=cid,
            source_uom_id=src.id,
            target_uom_id=tgt.id,
        )
        assert found is not None
        assert found.conversion_factor == 1000.0

    def test_list_for_uom_returns_related_conversions(
        self, db_session: Session
    ) -> None:
        uom_repo = UOMRepository(db_session)
        conv_repo = UOMConversionRepository(db_session)
        cid = uuid.uuid4()
        kg = uom_repo.create(
            UOM(
                company_id=cid,
                code="KG2",
                name="KG",
                uom_type="WEIGHT",
                status="active",
            )
        )
        lb = uom_repo.create(
            UOM(
                company_id=cid,
                code="LB",
                name="Pound",
                uom_type="WEIGHT",
                status="active",
            )
        )
        conv_repo.create(
            UOMConversion(
                company_id=cid,
                source_uom_id=str(kg.id),
                target_uom_id=str(lb.id),
                conversion_factor=2.2046,
            )
        )
        results = conv_repo.list_for_uom(company_id=cid, uom_id=kg.id)
        assert len(results) >= 1


# =============================================================================
# TagRepository
# =============================================================================


class TestTagRepository:
    def test_create_and_get_by_name(self, db_session: Session) -> None:
        repo = TagRepository(db_session)
        cid = uuid.uuid4()
        tag = repo.create(Tag(company_id=cid, name="Sale", usage_count=0))
        found = repo.get_by_name(company_id=cid, name="Sale")
        assert found is not None
        assert found.id == tag.id

    def test_get_by_name_returns_none_when_missing(self, db_session: Session) -> None:
        repo = TagRepository(db_session)
        assert repo.get_by_name(company_id=uuid.uuid4(), name="Missing") is None

    def test_list_all_excludes_other_companies(self, db_session: Session) -> None:
        repo = TagRepository(db_session)
        cid_a, cid_b = uuid.uuid4(), uuid.uuid4()
        repo.create(Tag(company_id=cid_a, name="TagA", usage_count=0))
        repo.create(Tag(company_id=cid_b, name="TagB", usage_count=0))
        tags_a = repo.list_all(company_id=cid_a)
        assert all(str(t.company_id) == str(cid_a) for t in tags_a)

    def test_get_by_ids_returns_matching_tags(self, db_session: Session) -> None:
        repo = TagRepository(db_session)
        cid = uuid.uuid4()
        t1 = repo.create(Tag(company_id=cid, name="T1", usage_count=0))
        t2 = repo.create(Tag(company_id=cid, name="T2", usage_count=0))
        repo.create(Tag(company_id=cid, name="T3", usage_count=0))
        results = repo.get_by_ids(
            company_id=cid,
            ids=[t1.id, t2.id],
        )
        result_ids = {r.id for r in results}
        assert t1.id in result_ids
        assert t2.id in result_ids

    def test_soft_delete_hides_from_list(self, db_session: Session) -> None:
        repo = TagRepository(db_session)
        cid = uuid.uuid4()
        tag = repo.create(Tag(company_id=cid, name="DeleteMe", usage_count=0))
        repo.soft_delete(id=tag.id, company_id=cid)
        tags = repo.list_all(company_id=cid)
        assert not any(t.id == tag.id for t in tags)


# =============================================================================
# ReasonCodeRepository
# =============================================================================


class TestReasonCodeRepository:
    def test_create_and_get_by_code(self, db_session: Session) -> None:
        repo = ReasonCodeRepository(db_session)
        cid = uuid.uuid4()
        rc = repo.create(
            ReasonCode(
                company_id=cid,
                code="DMG01",
                label="Physical Damage",
                applies_to="DAMAGE",
                is_active=True,
            )
        )
        found = repo.get_by_code(company_id=cid, code="DMG01")
        assert found is not None
        assert found.id == rc.id

    def test_list_by_applies_to_filters(self, db_session: Session) -> None:
        repo = ReasonCodeRepository(db_session)
        cid = uuid.uuid4()
        repo.create(
            ReasonCode(
                company_id=cid,
                code="ADJ1",
                label="Adj",
                applies_to="ADJUSTMENT",
                is_active=True,
            )
        )
        repo.create(
            ReasonCode(
                company_id=cid,
                code="DMG1",
                label="Dmg",
                applies_to="DAMAGE",
                is_active=True,
            )
        )
        adj = repo.list_by_applies_to(company_id=cid, applies_to="ADJUSTMENT")
        assert all(r.applies_to == "ADJUSTMENT" for r in adj)
        assert len(adj) == 1

    def test_list_by_applies_to_active_only(self, db_session: Session) -> None:
        repo = ReasonCodeRepository(db_session)
        cid = uuid.uuid4()
        repo.create(
            ReasonCode(
                company_id=cid,
                code="A1",
                label="Active",
                applies_to="RETURN",
                is_active=True,
            )
        )
        repo.create(
            ReasonCode(
                company_id=cid,
                code="A2",
                label="Inactive",
                applies_to="RETURN",
                is_active=False,
            )
        )
        active = repo.list_by_applies_to(
            company_id=cid, applies_to="RETURN", active_only=True
        )
        assert all(r.is_active for r in active)
        assert len(active) == 1

    def test_get_by_code_isolates_by_company(self, db_session: Session) -> None:
        repo = ReasonCodeRepository(db_session)
        cid_a, cid_b = uuid.uuid4(), uuid.uuid4()
        repo.create(
            ReasonCode(
                company_id=cid_a,
                code="RC",
                label="L",
                applies_to="DAMAGE",
                is_active=True,
            )
        )
        result_b = repo.get_by_code(company_id=cid_b, code="RC")
        assert result_b is None


# =============================================================================
# CustomFieldDefinitionRepository
# =============================================================================


class TestCustomFieldDefinitionRepository:
    def test_create_and_get_by_field_key(self, db_session: Session) -> None:
        repo = CustomFieldDefinitionRepository(db_session)
        cid = uuid.uuid4()
        cf = repo.create(
            CustomFieldDefinition(
                company_id=cid,
                entity_type="PRODUCT",
                field_key="serial_no",
                field_label="Serial Number",
                data_type="TEXT",
                is_required=False,
                sort_order=0,
            )
        )
        found = repo.get_by_field_key(
            company_id=cid, entity_type="PRODUCT", field_key="serial_no"
        )
        assert found is not None
        assert found.id == cf.id

    def test_list_for_entity_type_filters(self, db_session: Session) -> None:
        repo = CustomFieldDefinitionRepository(db_session)
        cid = uuid.uuid4()
        repo.create(
            CustomFieldDefinition(
                company_id=cid,
                entity_type="PRODUCT",
                field_key="f1",
                field_label="F1",
                data_type="TEXT",
                is_required=False,
                sort_order=0,
            )
        )
        repo.create(
            CustomFieldDefinition(
                company_id=cid,
                entity_type="WAREHOUSE",
                field_key="f2",
                field_label="F2",
                data_type="TEXT",
                is_required=False,
                sort_order=0,
            )
        )
        products = repo.list_for_entity_type(company_id=cid, entity_type="PRODUCT")
        assert all(f.entity_type == "PRODUCT" for f in products)
        assert len(products) == 1

    def test_get_by_field_key_isolates_by_company(self, db_session: Session) -> None:
        repo = CustomFieldDefinitionRepository(db_session)
        cid_a, cid_b = uuid.uuid4(), uuid.uuid4()
        repo.create(
            CustomFieldDefinition(
                company_id=cid_a,
                entity_type="PRODUCT",
                field_key="my_key",
                field_label="My Key",
                data_type="TEXT",
                is_required=False,
                sort_order=0,
            )
        )
        result = repo.get_by_field_key(
            company_id=cid_b, entity_type="PRODUCT", field_key="my_key"
        )
        assert result is None


# =============================================================================
# AttributeDefinitionRepository
# =============================================================================


class TestAttributeDefinitionRepository:
    def test_create_and_get_by_name(self, db_session: Session) -> None:
        repo = AttributeDefinitionRepository(db_session)
        cid = uuid.uuid4()
        attr = repo.create(
            AttributeDefinition(
                company_id=cid, name="Color", data_type="DROPDOWN", is_required=False
            )
        )
        found = repo.get_by_name(company_id=cid, name="Color")
        assert found is not None
        assert found.id == attr.id

    def test_list_active_excludes_deleted(self, db_session: Session) -> None:
        repo = AttributeDefinitionRepository(db_session)
        cid = uuid.uuid4()
        a1 = repo.create(
            AttributeDefinition(
                company_id=cid, name="Size", data_type="TEXT", is_required=False
            )
        )
        a2 = repo.create(
            AttributeDefinition(
                company_id=cid, name="Weight", data_type="NUMBER", is_required=False
            )
        )
        repo.soft_delete(id=a2.id, company_id=cid)
        active = repo.list_active(company_id=cid)
        active_ids = {a.id for a in active}
        assert a1.id in active_ids
        assert a2.id not in active_ids


# =============================================================================
# AttributeSetRepository + AttributeSetMembershipRepository
# =============================================================================


class TestAttributeSetRepository:
    def test_create_and_get_by_name(self, db_session: Session) -> None:
        repo = AttributeSetRepository(db_session)
        cid = uuid.uuid4()
        attr_set = repo.create(
            AttributeSet(company_id=cid, name="Electronics Set", scope="PRODUCT_TYPE")
        )
        found = repo.get_by_name(company_id=cid, name="Electronics Set")
        assert found is not None
        assert found.id == attr_set.id

    def test_list_by_scope_filters(self, db_session: Session) -> None:
        repo = AttributeSetRepository(db_session)
        cid = uuid.uuid4()
        repo.create(AttributeSet(company_id=cid, name="PT Set", scope="PRODUCT_TYPE"))
        repo.create(AttributeSet(company_id=cid, name="Cat Set", scope="CATEGORY"))
        pt_sets = repo.list_by_scope(company_id=cid, scope="PRODUCT_TYPE")
        assert all(s.scope == "PRODUCT_TYPE" for s in pt_sets)
        assert len(pt_sets) == 1

    def test_tenant_isolation(self, db_session: Session) -> None:
        repo = AttributeSetRepository(db_session)
        cid_a, cid_b = uuid.uuid4(), uuid.uuid4()
        repo.create(AttributeSet(company_id=cid_a, name="Set A", scope="CATEGORY"))
        result = repo.get_by_name(company_id=cid_b, name="Set A")
        assert result is None


class TestAttributeSetMembershipRepository:
    def test_add_and_list_memberships(self, db_session: Session) -> None:
        set_repo = AttributeSetRepository(db_session)
        attr_repo = AttributeDefinitionRepository(db_session)
        mem_repo = AttributeSetMembershipRepository(db_session)
        cid = uuid.uuid4()
        attr_set = set_repo.create(
            AttributeSet(company_id=cid, name="My Set", scope="PRODUCT_TYPE")
        )
        attr = attr_repo.create(
            AttributeDefinition(
                company_id=cid, name="Color2", data_type="TEXT", is_required=False
            )
        )
        membership = mem_repo.create(
            AttributeSetMembership(
                company_id=cid,
                attribute_set_id=str(attr_set.id),
                attribute_definition_id=str(attr.id),
                sort_order=0,
            )
        )
        assert membership.id is not None
        memberships = mem_repo.list_for_set(
            company_id=cid, attribute_set_id=attr_set.id
        )
        assert any(m.id == membership.id for m in memberships)

    def test_get_by_set_and_definition_returns_none_when_missing(
        self, db_session: Session
    ) -> None:
        mem_repo = AttributeSetMembershipRepository(db_session)
        result = mem_repo.get_by_set_and_definition(
            company_id=uuid.uuid4(),
            attribute_set_id=uuid.uuid4(),
            attribute_definition_id=uuid.uuid4(),
        )
        assert result is None
