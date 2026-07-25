"""Unit tests for master data services: Brand, UOM, UOMConversion, Tag, ReasonCode,
CustomField, AttributeDefinition, AttributeSet.

Tests all business invariants and conflict/not-found guard behaviours.

Spec ref: specs/005-inventory-management/spec.md §14
Task: T048
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from modules.inventory.exceptions import (
    AttributeNameConflictError,
    AttributeNotFoundError,
    AttributeSetNameConflictError,
    AttributeSetNotFoundError,
    BrandCodeConflictError,
    BrandNotFoundError,
    CustomFieldKeyConflictError,
    CustomFieldNotFoundError,
    ReasonCodeConflictError,
    ReasonCodeNotFoundError,
    TagNameConflictError,
    TagNotFoundError,
    UomCodeConflictError,
    UomConversionConflictError,
    UomNotFoundError,
)
from modules.inventory.services.master_data_service import (
    AttributeDefinitionService,
    AttributeSetService,
    BrandService,
    CustomFieldService,
    ReasonCodeService,
    TagService,
    UOMConversionService,
    UOMService,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_entity(**kwargs):
    m = MagicMock()
    for k, v in kwargs.items():
        setattr(m, k, v)
    return m


# =============================================================================
# BrandService
# =============================================================================


class TestBrandService:
    def _svc(self, repo=None):
        return BrandService(db=MagicMock(), brand_repo=repo or MagicMock())

    def test_create_raises_conflict_on_duplicate_code(self):
        repo = MagicMock()
        repo.get_by_code.return_value = _mock_entity()
        svc = self._svc(repo)
        with pytest.raises(BrandCodeConflictError):
            svc.create(company_id=uuid.uuid4(), code="BRAND1", name="Brand One")

    def test_create_succeeds_when_code_unique(self):
        repo = MagicMock()
        repo.get_by_code.return_value = None
        brand = _mock_entity(id=str(uuid.uuid4()), code="BRAND1")
        repo.create.return_value = brand
        svc = self._svc(repo)
        result = svc.create(company_id=uuid.uuid4(), code="BRAND1", name="Brand One")
        assert result is brand

    def test_get_by_id_raises_not_found(self):
        from core.exceptions.base import NotFoundException

        repo = MagicMock()
        repo.get_by_id.side_effect = NotFoundException("not found")
        svc = self._svc(repo)
        with pytest.raises(BrandNotFoundError):
            svc.get_by_id(company_id=uuid.uuid4(), brand_id=uuid.uuid4())

    def test_deactivate_is_idempotent_when_already_inactive(self):
        repo = MagicMock()
        brand = _mock_entity(status="inactive")
        repo.get_by_id.return_value = brand
        svc = self._svc(repo)
        result = svc.deactivate(company_id=uuid.uuid4(), brand_id=uuid.uuid4())
        repo.update.assert_not_called()
        assert result is brand

    def test_deactivate_sets_inactive(self):
        repo = MagicMock()
        brand = _mock_entity(status="active")
        repo.get_by_id.return_value = brand
        repo.update.return_value = brand
        svc = self._svc(repo)
        svc.deactivate(company_id=uuid.uuid4(), brand_id=uuid.uuid4())
        assert brand.status == "inactive"

    def test_activate_sets_active(self):
        repo = MagicMock()
        brand = _mock_entity(status="inactive")
        repo.get_by_id.return_value = brand
        repo.update.return_value = brand
        svc = self._svc(repo)
        svc.activate(company_id=uuid.uuid4(), brand_id=uuid.uuid4())
        assert brand.status == "active"

    def test_update_raises_conflict_on_code_change(self):
        repo = MagicMock()
        brand = _mock_entity(code="OLD")
        repo.get_by_id.return_value = brand
        repo.get_by_code.return_value = _mock_entity()  # conflict
        svc = self._svc(repo)
        with pytest.raises(BrandCodeConflictError):
            svc.update(company_id=uuid.uuid4(), brand_id=uuid.uuid4(), code="NEW")

    def test_delete_raises_not_found_on_failure(self):
        repo = MagicMock()
        repo.soft_delete.side_effect = Exception("gone")
        svc = self._svc(repo)
        with pytest.raises(BrandNotFoundError):
            svc.delete(company_id=uuid.uuid4(), brand_id=uuid.uuid4())


# =============================================================================
# UOMService
# =============================================================================


class TestUOMService:
    def _svc(self, repo=None):
        return UOMService(db=MagicMock(), uom_repo=repo or MagicMock())

    def test_create_raises_conflict_on_duplicate_code(self):
        repo = MagicMock()
        repo.get_by_code.return_value = _mock_entity()
        svc = self._svc(repo)
        with pytest.raises(UomCodeConflictError):
            svc.create(
                company_id=uuid.uuid4(), code="KG", name="Kilogram", uom_type="WEIGHT"
            )

    def test_create_raises_value_error_on_invalid_type(self):
        repo = MagicMock()
        repo.get_by_code.return_value = None
        svc = self._svc(repo)
        with pytest.raises(ValueError, match="uom_type"):
            svc.create(company_id=uuid.uuid4(), code="X", name="X", uom_type="INVALID")

    def test_create_succeeds_with_valid_inputs(self):
        repo = MagicMock()
        repo.get_by_code.return_value = None
        uom = _mock_entity(code="KG", uom_type="WEIGHT")
        repo.create.return_value = uom
        svc = self._svc(repo)
        result = svc.create(
            company_id=uuid.uuid4(), code="KG", name="Kilogram", uom_type="WEIGHT"
        )
        assert result is uom

    def test_get_by_id_raises_not_found(self):
        from core.exceptions.base import NotFoundException

        repo = MagicMock()
        repo.get_by_id.side_effect = NotFoundException("x")
        svc = self._svc(repo)
        with pytest.raises(UomNotFoundError):
            svc.get_by_id(company_id=uuid.uuid4(), uom_id=uuid.uuid4())

    def test_deactivate_idempotent_when_inactive(self):
        repo = MagicMock()
        uom = _mock_entity(status="inactive")
        repo.get_by_id.return_value = uom
        svc = self._svc(repo)
        result = svc.deactivate(company_id=uuid.uuid4(), uom_id=uuid.uuid4())
        repo.update.assert_not_called()
        assert result is uom

    def test_all_valid_uom_types_accepted(self):
        for t in ("UNIT", "WEIGHT", "VOLUME", "LENGTH", "AREA"):
            repo = MagicMock()
            repo.get_by_code.return_value = None
            repo.create.return_value = _mock_entity(uom_type=t)
            svc = self._svc(repo)
            result = svc.create(company_id=uuid.uuid4(), code="X", name="X", uom_type=t)
            assert result is not None


# =============================================================================
# UOMConversionService
# =============================================================================


class TestUOMConversionService:
    def _svc(self, uom_repo=None, conv_repo=None):
        return UOMConversionService(
            db=MagicMock(),
            uom_repo=uom_repo or MagicMock(),
            conversion_repo=conv_repo or MagicMock(),
        )

    def test_create_raises_value_error_for_zero_factor(self):
        svc = self._svc()
        with pytest.raises(ValueError, match="greater than zero"):
            svc.create(
                company_id=uuid.uuid4(),
                source_uom_id=uuid.uuid4(),
                target_uom_id=uuid.uuid4(),
                conversion_factor=0,
            )

    def test_create_raises_value_error_for_negative_factor(self):
        svc = self._svc()
        with pytest.raises(ValueError):
            svc.create(
                company_id=uuid.uuid4(),
                source_uom_id=uuid.uuid4(),
                target_uom_id=uuid.uuid4(),
                conversion_factor=-5.0,
            )

    def test_create_raises_uom_not_found_for_missing_source(self):
        from core.exceptions.base import NotFoundException

        uom_repo = MagicMock()
        uom_repo.get_by_id.side_effect = NotFoundException("x")
        svc = self._svc(uom_repo=uom_repo)
        with pytest.raises(UomNotFoundError):
            svc.create(
                company_id=uuid.uuid4(),
                source_uom_id=uuid.uuid4(),
                target_uom_id=uuid.uuid4(),
                conversion_factor=1.5,
            )

    def test_create_raises_conflict_when_pair_exists(self):
        uom_repo = MagicMock()  # get_by_id succeeds both times
        conv_repo = MagicMock()
        conv_repo.get_by_pair.return_value = _mock_entity()
        svc = self._svc(uom_repo=uom_repo, conv_repo=conv_repo)
        with pytest.raises(UomConversionConflictError):
            svc.create(
                company_id=uuid.uuid4(),
                source_uom_id=uuid.uuid4(),
                target_uom_id=uuid.uuid4(),
                conversion_factor=2.0,
            )

    def test_create_succeeds_with_valid_inputs(self):
        uom_repo = MagicMock()
        conv_repo = MagicMock()
        conv_repo.get_by_pair.return_value = None
        conversion = _mock_entity(conversion_factor=2.0)
        conv_repo.create.return_value = conversion
        svc = self._svc(uom_repo=uom_repo, conv_repo=conv_repo)
        result = svc.create(
            company_id=uuid.uuid4(),
            source_uom_id=uuid.uuid4(),
            target_uom_id=uuid.uuid4(),
            conversion_factor=2.0,
        )
        assert result is conversion


# =============================================================================
# TagService
# =============================================================================


class TestTagService:
    def _svc(self, repo=None):
        return TagService(db=MagicMock(), tag_repo=repo or MagicMock())

    def test_create_raises_conflict_on_duplicate_name(self):
        repo = MagicMock()
        repo.get_by_name.return_value = _mock_entity()
        svc = self._svc(repo)
        with pytest.raises(TagNameConflictError):
            svc.create(company_id=uuid.uuid4(), name="Sale")

    def test_create_succeeds_when_name_unique(self):
        repo = MagicMock()
        repo.get_by_name.return_value = None
        tag = _mock_entity(name="Sale", usage_count=0)
        repo.create.return_value = tag
        svc = self._svc(repo)
        result = svc.create(company_id=uuid.uuid4(), name="Sale")
        assert result is tag

    def test_get_by_id_raises_not_found(self):
        from core.exceptions.base import NotFoundException

        repo = MagicMock()
        repo.get_by_id.side_effect = NotFoundException("x")
        svc = self._svc(repo)
        with pytest.raises(TagNotFoundError):
            svc.get_by_id(company_id=uuid.uuid4(), tag_id=uuid.uuid4())

    def test_update_raises_conflict_on_name_change(self):
        repo = MagicMock()
        tag = _mock_entity(name="Old")
        repo.get_by_id.return_value = tag
        repo.get_by_name.return_value = _mock_entity()
        svc = self._svc(repo)
        with pytest.raises(TagNameConflictError):
            svc.update(company_id=uuid.uuid4(), tag_id=uuid.uuid4(), name="New")

    def test_delete_raises_not_found_on_failure(self):
        repo = MagicMock()
        repo.soft_delete.side_effect = Exception("gone")
        svc = self._svc(repo)
        with pytest.raises(TagNotFoundError):
            svc.delete(company_id=uuid.uuid4(), tag_id=uuid.uuid4())


# =============================================================================
# ReasonCodeService
# =============================================================================


class TestReasonCodeService:
    def _svc(self, repo=None):
        return ReasonCodeService(db=MagicMock(), reason_code_repo=repo or MagicMock())

    def test_create_raises_value_error_on_invalid_applies_to(self):
        repo = MagicMock()
        repo.get_by_code.return_value = None
        svc = self._svc(repo)
        with pytest.raises(ValueError, match="applies_to"):
            svc.create(
                company_id=uuid.uuid4(), code="RC1", label="L", applies_to="INVALID"
            )

    def test_create_raises_conflict_on_duplicate_code(self):
        repo = MagicMock()
        repo.get_by_code.return_value = _mock_entity()
        svc = self._svc(repo)
        with pytest.raises(ReasonCodeConflictError):
            svc.create(
                company_id=uuid.uuid4(), code="RC1", label="L", applies_to="ADJUSTMENT"
            )

    def test_create_succeeds_with_valid_inputs(self):
        repo = MagicMock()
        repo.get_by_code.return_value = None
        rc = _mock_entity(code="RC1", is_active=True)
        repo.create.return_value = rc
        svc = self._svc(repo)
        result = svc.create(
            company_id=uuid.uuid4(), code="RC1", label="Reason", applies_to="ADJUSTMENT"
        )
        assert result is rc

    def test_deactivate_idempotent_when_already_inactive(self):
        repo = MagicMock()
        rc = _mock_entity(is_active=False)
        repo.get_by_id.return_value = rc
        svc = self._svc(repo)
        result = svc.deactivate(company_id=uuid.uuid4(), reason_code_id=uuid.uuid4())
        repo.update.assert_not_called()
        assert result is rc

    def test_all_applies_to_values_accepted(self):
        for v in ("ADJUSTMENT", "DAMAGE", "RETURN"):
            repo = MagicMock()
            repo.get_by_code.return_value = None
            repo.create.return_value = _mock_entity(applies_to=v, is_active=True)
            svc = self._svc(repo)
            result = svc.create(
                company_id=uuid.uuid4(), code="X", label="X", applies_to=v
            )
            assert result is not None

    def test_get_by_id_raises_not_found(self):
        from core.exceptions.base import NotFoundException

        repo = MagicMock()
        repo.get_by_id.side_effect = NotFoundException("x")
        svc = self._svc(repo)
        with pytest.raises(ReasonCodeNotFoundError):
            svc.get_by_id(company_id=uuid.uuid4(), reason_code_id=uuid.uuid4())


# =============================================================================
# CustomFieldService
# =============================================================================


class TestCustomFieldService:
    def _svc(self, repo=None):
        return CustomFieldService(db=MagicMock(), custom_field_repo=repo or MagicMock())

    def test_create_raises_value_error_on_invalid_entity_type(self):
        repo = MagicMock()
        svc = self._svc(repo)
        with pytest.raises(ValueError, match="entity_type"):
            svc.create(
                company_id=uuid.uuid4(),
                entity_type="INVALID",
                field_key="key",
                field_label="Label",
                data_type="TEXT",
            )

    def test_create_raises_value_error_on_invalid_data_type(self):
        repo = MagicMock()
        svc = self._svc(repo)
        with pytest.raises(ValueError, match="data_type"):
            svc.create(
                company_id=uuid.uuid4(),
                entity_type="PRODUCT",
                field_key="key",
                field_label="Label",
                data_type="BADTYPE",
            )

    def test_create_raises_conflict_on_duplicate_field_key(self):
        repo = MagicMock()
        repo.get_by_field_key.return_value = _mock_entity()
        svc = self._svc(repo)
        with pytest.raises(CustomFieldKeyConflictError):
            svc.create(
                company_id=uuid.uuid4(),
                entity_type="PRODUCT",
                field_key="warranty_type",
                field_label="Warranty",
                data_type="TEXT",
            )

    def test_create_succeeds_with_valid_inputs(self):
        repo = MagicMock()
        repo.get_by_field_key.return_value = None
        cf = _mock_entity(field_key="warranty_type")
        repo.create.return_value = cf
        svc = self._svc(repo)
        result = svc.create(
            company_id=uuid.uuid4(),
            entity_type="PRODUCT",
            field_key="warranty_type",
            field_label="Warranty Type",
            data_type="TEXT",
        )
        assert result is cf

    def test_get_by_id_raises_not_found(self):
        from core.exceptions.base import NotFoundException

        repo = MagicMock()
        repo.get_by_id.side_effect = NotFoundException("x")
        svc = self._svc(repo)
        with pytest.raises(CustomFieldNotFoundError):
            svc.get_by_id(company_id=uuid.uuid4(), field_id=uuid.uuid4())

    def test_delete_raises_not_found_on_failure(self):
        repo = MagicMock()
        repo.soft_delete.side_effect = Exception("gone")
        svc = self._svc(repo)
        with pytest.raises(CustomFieldNotFoundError):
            svc.delete(company_id=uuid.uuid4(), field_id=uuid.uuid4())


# =============================================================================
# AttributeDefinitionService
# =============================================================================


class TestAttributeDefinitionService:
    def _svc(self, repo=None):
        return AttributeDefinitionService(db=MagicMock(), attr_repo=repo or MagicMock())

    def test_create_raises_conflict_on_duplicate_name(self):
        repo = MagicMock()
        repo.get_by_name.return_value = _mock_entity()
        svc = self._svc(repo)
        with pytest.raises(AttributeNameConflictError):
            svc.create(company_id=uuid.uuid4(), name="Color", data_type="TEXT")

    def test_create_raises_value_error_on_invalid_data_type(self):
        repo = MagicMock()
        repo.get_by_name.return_value = None
        svc = self._svc(repo)
        with pytest.raises(ValueError, match="data_type"):
            svc.create(company_id=uuid.uuid4(), name="Color", data_type="INVALID")

    def test_create_succeeds(self):
        repo = MagicMock()
        repo.get_by_name.return_value = None
        attr = _mock_entity(name="Color", data_type="TEXT")
        repo.create.return_value = attr
        svc = self._svc(repo)
        result = svc.create(company_id=uuid.uuid4(), name="Color", data_type="TEXT")
        assert result is attr

    def test_get_by_id_raises_not_found(self):
        from core.exceptions.base import NotFoundException

        repo = MagicMock()
        repo.get_by_id.side_effect = NotFoundException("x")
        svc = self._svc(repo)
        with pytest.raises(AttributeNotFoundError):
            svc.get_by_id(company_id=uuid.uuid4(), attr_id=uuid.uuid4())


# =============================================================================
# AttributeSetService
# =============================================================================


class TestAttributeSetService:
    def _svc(self, set_repo=None, mem_repo=None, attr_repo=None):
        return AttributeSetService(
            db=MagicMock(),
            attr_set_repo=set_repo or MagicMock(),
            membership_repo=mem_repo or MagicMock(),
            attr_repo=attr_repo or MagicMock(),
        )

    def test_create_raises_conflict_on_duplicate_name(self):
        set_repo = MagicMock()
        set_repo.get_by_name.return_value = _mock_entity()
        svc = self._svc(set_repo=set_repo)
        with pytest.raises(AttributeSetNameConflictError):
            svc.create(
                company_id=uuid.uuid4(), name="Electronics", scope="PRODUCT_TYPE"
            )

    def test_create_raises_value_error_on_invalid_scope(self):
        set_repo = MagicMock()
        set_repo.get_by_name.return_value = None
        svc = self._svc(set_repo=set_repo)
        with pytest.raises(ValueError, match="scope"):
            svc.create(company_id=uuid.uuid4(), name="Set", scope="BADSCOPE")

    def test_create_succeeds_with_valid_scope(self):
        for scope in ("PRODUCT_TYPE", "CATEGORY"):
            set_repo = MagicMock()
            set_repo.get_by_name.return_value = None
            attr_set = _mock_entity(name="Set", scope=scope)
            set_repo.create.return_value = attr_set
            svc = self._svc(set_repo=set_repo)
            result = svc.create(company_id=uuid.uuid4(), name="Set", scope=scope)
            assert result is attr_set

    def test_get_by_id_raises_not_found(self):
        from core.exceptions.base import NotFoundException

        set_repo = MagicMock()
        set_repo.get_by_id.side_effect = NotFoundException("x")
        svc = self._svc(set_repo=set_repo)
        with pytest.raises(AttributeSetNotFoundError):
            svc.get_by_id(company_id=uuid.uuid4(), attr_set_id=uuid.uuid4())

    def test_add_attribute_is_idempotent_when_already_exists(self):
        set_repo = MagicMock()
        set_repo.get_by_id.return_value = _mock_entity()
        mem_repo = MagicMock()
        existing = _mock_entity()
        mem_repo.get_by_set_and_definition.return_value = existing
        svc = self._svc(set_repo=set_repo, mem_repo=mem_repo)
        result = svc.add_attribute(
            company_id=uuid.uuid4(),
            attr_set_id=uuid.uuid4(),
            attr_definition_id=uuid.uuid4(),
        )
        mem_repo.create.assert_not_called()
        assert result is existing

    def test_remove_attribute_is_idempotent_when_not_found(self):
        set_repo = MagicMock()
        mem_repo = MagicMock()
        mem_repo.get_by_set_and_definition.return_value = None
        svc = self._svc(set_repo=set_repo, mem_repo=mem_repo)
        # Should not raise
        svc.remove_attribute(
            company_id=uuid.uuid4(),
            attr_set_id=uuid.uuid4(),
            attr_definition_id=uuid.uuid4(),
        )
        mem_repo.soft_delete.assert_not_called()
