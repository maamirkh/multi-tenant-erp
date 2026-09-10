"""MasterDataService — CRUD services for all Phase 1 master data entities.

Covers: Brand, UOM, UOMConversion, Tag, ReasonCode, CustomFieldDefinition,
        AttributeDefinition, AttributeSet, AttributeSetMembership.

Spec ref: specs/005-inventory-management/spec.md §14
Data model: specs/005-inventory-management/data-model.md §1.2
"""

from __future__ import annotations

import builtins
import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

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

logger = logging.getLogger(__name__)

_VALID_UOM_TYPES = frozenset({"UNIT", "WEIGHT", "VOLUME", "LENGTH", "AREA"})
_VALID_APPLIES_TO = frozenset({"ADJUSTMENT", "DAMAGE", "RETURN"})
_VALID_ENTITY_TYPES = frozenset({"PRODUCT", "WAREHOUSE", "CATEGORY", "BRAND"})
_VALID_DATA_TYPES = frozenset(
    {"TEXT", "NUMBER", "BOOLEAN", "DATE", "DROPDOWN", "MULTISELECT"}
)
_VALID_ATTR_DATA_TYPES = frozenset(
    {"TEXT", "NUMBER", "BOOLEAN", "DATE", "DROPDOWN", "MULTISELECT"}
)
_VALID_SCOPES = frozenset({"PRODUCT_TYPE", "CATEGORY"})


# =============================================================================
# BrandService
# =============================================================================


class BrandService:
    """Application service for brand master data management."""

    def __init__(self, db: Session, brand_repo: BrandRepository) -> None:
        self.db = db
        self._repo = brand_repo

    def create(
        self,
        company_id: UUID,
        code: str,
        name: str,
        country_of_origin: str | None = None,
        logo_url: str | None = None,
        website: str | None = None,
        actor_id: UUID | None = None,
    ) -> Brand:
        """Create a new brand.

        Raises:
            BrandCodeConflictError: If code already exists for this company.
        """
        if self._repo.get_by_code(company_id=company_id, code=code):
            raise BrandCodeConflictError(
                message=f"A brand with code '{code}' already exists.",
                details={"code": code},
            )
        brand = Brand(
            company_id=company_id,
            code=code,
            name=name,
            country_of_origin=country_of_origin,
            logo_url=logo_url,
            website=website,
            status="active",
            created_by=actor_id,
        )
        result = self._repo.create(brand)
        logger.info(
            "Brand created: id=%s code=%s company=%s", result.id, code, company_id
        )
        return result

    def get_by_id(self, company_id: UUID, brand_id: UUID) -> Brand:
        """Return brand by ID or raise BrandNotFoundError."""
        from core.exceptions.base import NotFoundException

        try:
            return self._repo.get_by_id(id=brand_id, company_id=company_id)
        except NotFoundException:
            raise BrandNotFoundError(details={"brand_id": str(brand_id)})

    def list(
        self, company_id: UUID, skip: int = 0, limit: int = 20
    ) -> tuple[list[Brand], int]:
        """Return paginated list of brands for the company."""
        return self._repo.list(company_id=company_id, skip=skip, limit=limit)

    def update(
        self,
        company_id: UUID,
        brand_id: UUID,
        name: str | None = None,
        country_of_origin: str | None = None,
        logo_url: str | None = None,
        website: str | None = None,
        code: str | None = None,
    ) -> Brand:
        """Update brand fields.

        Raises:
            BrandNotFoundError: If brand does not exist.
            BrandCodeConflictError: If new code conflicts.
        """
        brand = self.get_by_id(company_id=company_id, brand_id=brand_id)
        if code is not None and code != brand.code:
            if self._repo.get_by_code(company_id=company_id, code=code):
                raise BrandCodeConflictError(
                    message=f"A brand with code '{code}' already exists.",
                    details={"code": code},
                )
            brand.code = code
        if name is not None:
            brand.name = name
        if country_of_origin is not None:
            brand.country_of_origin = country_of_origin
        if logo_url is not None:
            brand.logo_url = logo_url
        if website is not None:
            brand.website = website
        return self._repo.update(brand)

    def deactivate(self, company_id: UUID, brand_id: UUID) -> Brand:
        """Deactivate a brand. Idempotent if already inactive."""
        brand = self.get_by_id(company_id=company_id, brand_id=brand_id)
        if brand.status == "inactive":
            return brand
        brand.status = "inactive"
        return self._repo.update(brand)

    def activate(self, company_id: UUID, brand_id: UUID) -> Brand:
        """Re-activate an inactive brand."""
        brand = self.get_by_id(company_id=company_id, brand_id=brand_id)
        if brand.status == "active":
            return brand
        brand.status = "active"
        return self._repo.update(brand)

    def delete(self, company_id: UUID, brand_id: UUID) -> None:
        """Soft-delete a brand.

        Raises:
            BrandNotFoundError: If brand does not exist.
        """
        try:
            self._repo.soft_delete(id=brand_id, company_id=company_id)
        except Exception:
            raise BrandNotFoundError(details={"brand_id": str(brand_id)})


# =============================================================================
# UOMService
# =============================================================================


class UOMService:
    """Application service for unit-of-measure master data management."""

    def __init__(self, db: Session, uom_repo: UOMRepository) -> None:
        self.db = db
        self._repo = uom_repo

    def create(
        self,
        company_id: UUID,
        code: str,
        name: str,
        uom_type: str,
        symbol: str | None = None,
        actor_id: UUID | None = None,
    ) -> UOM:
        """Create a new unit of measure.

        Raises:
            UomCodeConflictError: If code already exists for this company.
            ValueError: If uom_type is not valid.
        """
        if uom_type not in _VALID_UOM_TYPES:
            raise ValueError(
                f"Invalid uom_type '{uom_type}'. Must be one of: {sorted(_VALID_UOM_TYPES)}"
            )
        if self._repo.get_by_code(company_id=company_id, code=code):
            raise UomCodeConflictError(
                message=f"A unit of measure with code '{code}' already exists.",
                details={"code": code},
            )
        uom = UOM(
            company_id=company_id,
            code=code,
            name=name,
            uom_type=uom_type,
            symbol=symbol,
            status="active",
            created_by=actor_id,
        )
        result = self._repo.create(uom)
        logger.info(
            "UOM created: id=%s code=%s company=%s", result.id, code, company_id
        )
        return result

    def get_by_id(self, company_id: UUID, uom_id: UUID) -> UOM:
        """Return UOM by ID or raise UomNotFoundError."""
        from core.exceptions.base import NotFoundException

        try:
            return self._repo.get_by_id(id=uom_id, company_id=company_id)
        except NotFoundException:
            raise UomNotFoundError(details={"uom_id": str(uom_id)})

    def list(
        self, company_id: UUID, skip: int = 0, limit: int = 20
    ) -> tuple[list[UOM], int]:
        """Return paginated list of UOMs for the company."""
        return self._repo.list(company_id=company_id, skip=skip, limit=limit)

    def update(
        self,
        company_id: UUID,
        uom_id: UUID,
        name: str | None = None,
        symbol: str | None = None,
        code: str | None = None,
    ) -> UOM:
        """Update UOM fields.

        Raises:
            UomNotFoundError: If UOM does not exist.
            UomCodeConflictError: If new code conflicts.
        """
        uom = self.get_by_id(company_id=company_id, uom_id=uom_id)
        if code is not None and code != uom.code:
            if self._repo.get_by_code(company_id=company_id, code=code):
                raise UomCodeConflictError(
                    message=f"A unit of measure with code '{code}' already exists.",
                    details={"code": code},
                )
            uom.code = code
        if name is not None:
            uom.name = name
        if symbol is not None:
            uom.symbol = symbol
        return self._repo.update(uom)

    def deactivate(self, company_id: UUID, uom_id: UUID) -> UOM:
        """Deactivate a UOM. Idempotent if already inactive."""
        uom = self.get_by_id(company_id=company_id, uom_id=uom_id)
        if uom.status == "inactive":
            return uom
        uom.status = "inactive"
        return self._repo.update(uom)

    def activate(self, company_id: UUID, uom_id: UUID) -> UOM:
        """Re-activate an inactive UOM."""
        uom = self.get_by_id(company_id=company_id, uom_id=uom_id)
        if uom.status == "active":
            return uom
        uom.status = "active"
        return self._repo.update(uom)

    def delete(self, company_id: UUID, uom_id: UUID) -> None:
        """Soft-delete a UOM.

        Raises:
            UomNotFoundError: If UOM does not exist.
        """
        try:
            self._repo.soft_delete(id=uom_id, company_id=company_id)
        except Exception:
            raise UomNotFoundError(details={"uom_id": str(uom_id)})


# =============================================================================
# UOMConversionService
# =============================================================================


class UOMConversionService:
    """Application service for UOM conversion factor management."""

    def __init__(
        self,
        db: Session,
        uom_repo: UOMRepository,
        conversion_repo: UOMConversionRepository,
    ) -> None:
        self.db = db
        self._uom_repo = uom_repo
        self._repo = conversion_repo

    def create(
        self,
        company_id: UUID,
        source_uom_id: UUID,
        target_uom_id: UUID,
        conversion_factor: float,
        notes: str | None = None,
        actor_id: UUID | None = None,
    ) -> UOMConversion:
        """Create a UOM conversion.

        Raises:
            UomNotFoundError: If source or target UOM not found.
            UomConversionConflictError: If conversion pair already exists.
            ValueError: If conversion_factor <= 0.
        """
        from core.exceptions.base import NotFoundException

        if conversion_factor <= 0:
            raise ValueError("Conversion factor must be greater than zero.")
        try:
            self._uom_repo.get_by_id(id=source_uom_id, company_id=company_id)
        except NotFoundException:
            raise UomNotFoundError(details={"uom_id": str(source_uom_id)})
        try:
            self._uom_repo.get_by_id(id=target_uom_id, company_id=company_id)
        except NotFoundException:
            raise UomNotFoundError(details={"uom_id": str(target_uom_id)})
        if self._repo.get_by_pair(
            company_id=company_id,
            source_uom_id=source_uom_id,
            target_uom_id=target_uom_id,
        ):
            raise UomConversionConflictError(
                details={
                    "source_uom_id": str(source_uom_id),
                    "target_uom_id": str(target_uom_id),
                }
            )
        conversion = UOMConversion(
            company_id=company_id,
            source_uom_id=str(source_uom_id),
            target_uom_id=str(target_uom_id),
            conversion_factor=conversion_factor,
            notes=notes,
            created_by=actor_id,
        )
        result = self._repo.create(conversion)
        logger.info(
            "UOMConversion created: id=%s %s->%s factor=%s",
            result.id,
            source_uom_id,
            target_uom_id,
            conversion_factor,
        )
        return result

    def get_by_id(self, company_id: UUID, conversion_id: UUID) -> UOMConversion:
        """Return conversion by ID or raise UomNotFoundError."""
        from core.exceptions.base import NotFoundException

        try:
            return self._repo.get_by_id(id=conversion_id, company_id=company_id)
        except NotFoundException:
            raise UomNotFoundError(details={"conversion_id": str(conversion_id)})

    def list_for_uom(self, company_id: UUID, uom_id: UUID) -> list[UOMConversion]:
        """Return all conversions where uom_id is source or target."""
        return self._repo.list_for_uom(company_id=company_id, uom_id=uom_id)

    def delete(self, company_id: UUID, conversion_id: UUID) -> None:
        """Soft-delete a UOM conversion."""
        try:
            self._repo.soft_delete(id=conversion_id, company_id=company_id)
        except Exception:
            raise UomNotFoundError(details={"conversion_id": str(conversion_id)})


# =============================================================================
# TagService
# =============================================================================


class TagService:
    """Application service for product tag management."""

    def __init__(self, db: Session, tag_repo: TagRepository) -> None:
        self.db = db
        self._repo = tag_repo

    def create(
        self,
        company_id: UUID,
        name: str,
        color: str | None = None,
        actor_id: UUID | None = None,
    ) -> Tag:
        """Create a new tag.

        Raises:
            TagNameConflictError: If tag name already exists for this company.
        """
        if self._repo.get_by_name(company_id=company_id, name=name):
            raise TagNameConflictError(
                message=f"A tag named '{name}' already exists.",
                details={"name": name},
            )
        tag = Tag(
            company_id=company_id,
            name=name,
            color=color,
            usage_count=0,
            created_by=actor_id,
        )
        result = self._repo.create(tag)
        logger.info(
            "Tag created: id=%s name=%s company=%s", result.id, name, company_id
        )
        return result

    def get_by_id(self, company_id: UUID, tag_id: UUID) -> Tag:
        """Return tag by ID or raise TagNotFoundError."""
        from core.exceptions.base import NotFoundException

        try:
            return self._repo.get_by_id(id=tag_id, company_id=company_id)
        except NotFoundException:
            raise TagNotFoundError(details={"tag_id": str(tag_id)})

    def list(self, company_id: UUID) -> list[Tag]:
        """Return all tags for the company."""
        return self._repo.list_all(company_id=company_id)

    def update(
        self,
        company_id: UUID,
        tag_id: UUID,
        name: str | None = None,
        color: str | None = None,
    ) -> Tag:
        """Update tag fields.

        Raises:
            TagNotFoundError: If tag does not exist.
            TagNameConflictError: If new name conflicts.
        """
        tag = self.get_by_id(company_id=company_id, tag_id=tag_id)
        if name is not None and name != tag.name:
            if self._repo.get_by_name(company_id=company_id, name=name):
                raise TagNameConflictError(
                    message=f"A tag named '{name}' already exists.",
                    details={"name": name},
                )
            tag.name = name
        if color is not None:
            tag.color = color
        return self._repo.update(tag)

    def delete(self, company_id: UUID, tag_id: UUID) -> None:
        """Soft-delete a tag.

        Raises:
            TagNotFoundError: If tag does not exist.
        """
        try:
            self._repo.soft_delete(id=tag_id, company_id=company_id)
        except Exception:
            raise TagNotFoundError(details={"tag_id": str(tag_id)})


# =============================================================================
# ReasonCodeService
# =============================================================================


class ReasonCodeService:
    """Application service for adjustment/damage/return reason codes."""

    def __init__(self, db: Session, reason_code_repo: ReasonCodeRepository) -> None:
        self.db = db
        self._repo = reason_code_repo

    def create(
        self,
        company_id: UUID,
        code: str,
        label: str,
        applies_to: str,
        description: str | None = None,
        actor_id: UUID | None = None,
    ) -> ReasonCode:
        """Create a reason code.

        Raises:
            ReasonCodeConflictError: If code already exists for this company.
            ValueError: If applies_to is invalid.
        """
        if applies_to not in _VALID_APPLIES_TO:
            raise ValueError(
                f"Invalid applies_to '{applies_to}'. Must be one of: {sorted(_VALID_APPLIES_TO)}"
            )
        if self._repo.get_by_code(company_id=company_id, code=code):
            raise ReasonCodeConflictError(
                message=f"A reason code '{code}' already exists.",
                details={"code": code},
            )
        reason_code = ReasonCode(
            company_id=company_id,
            code=code,
            label=label,
            applies_to=applies_to,
            description=description,
            is_active=True,
            created_by=actor_id,
        )
        result = self._repo.create(reason_code)
        logger.info(
            "ReasonCode created: id=%s code=%s company=%s", result.id, code, company_id
        )
        return result

    def get_by_id(self, company_id: UUID, reason_code_id: UUID) -> ReasonCode:
        """Return reason code by ID or raise ReasonCodeNotFoundError."""
        from core.exceptions.base import NotFoundException

        try:
            return self._repo.get_by_id(id=reason_code_id, company_id=company_id)
        except NotFoundException:
            raise ReasonCodeNotFoundError(
                details={"reason_code_id": str(reason_code_id)}
            )

    def list(
        self, company_id: UUID, skip: int = 0, limit: int = 20
    ) -> tuple[list[ReasonCode], int]:
        """Return paginated list of reason codes."""
        return self._repo.list(company_id=company_id, skip=skip, limit=limit)

    def update(
        self,
        company_id: UUID,
        reason_code_id: UUID,
        label: str | None = None,
        description: str | None = None,
    ) -> ReasonCode:
        """Update reason code fields."""
        rc = self.get_by_id(company_id=company_id, reason_code_id=reason_code_id)
        if label is not None:
            rc.label = label
        if description is not None:
            rc.description = description
        return self._repo.update(rc)

    def deactivate(self, company_id: UUID, reason_code_id: UUID) -> ReasonCode:
        """Deactivate a reason code. Idempotent."""
        rc = self.get_by_id(company_id=company_id, reason_code_id=reason_code_id)
        if not rc.is_active:
            return rc
        rc.is_active = False
        return self._repo.update(rc)

    def activate(self, company_id: UUID, reason_code_id: UUID) -> ReasonCode:
        """Re-activate a reason code."""
        rc = self.get_by_id(company_id=company_id, reason_code_id=reason_code_id)
        if rc.is_active:
            return rc
        rc.is_active = True
        return self._repo.update(rc)

    def delete(self, company_id: UUID, reason_code_id: UUID) -> None:
        """Soft-delete a reason code."""
        try:
            self._repo.soft_delete(id=reason_code_id, company_id=company_id)
        except Exception:
            raise ReasonCodeNotFoundError(
                details={"reason_code_id": str(reason_code_id)}
            )


# =============================================================================
# CustomFieldService
# =============================================================================


class CustomFieldService:
    """Application service for custom field definitions."""

    def __init__(
        self, db: Session, custom_field_repo: CustomFieldDefinitionRepository
    ) -> None:
        self.db = db
        self._repo = custom_field_repo

    def create(
        self,
        company_id: UUID,
        entity_type: str,
        field_key: str,
        field_label: str,
        data_type: str,
        options: list[Any] | dict[str, Any] | None = None,
        is_required: bool = False,
        sort_order: int = 0,
        placeholder: str | None = None,
        actor_id: UUID | None = None,
    ) -> CustomFieldDefinition:
        """Create a custom field definition.

        Raises:
            CustomFieldKeyConflictError: If field_key already exists for entity_type.
            ValueError: If entity_type or data_type is invalid.
        """
        if entity_type not in _VALID_ENTITY_TYPES:
            raise ValueError(
                f"Invalid entity_type '{entity_type}'. Must be one of: {sorted(_VALID_ENTITY_TYPES)}"
            )
        if data_type not in _VALID_DATA_TYPES:
            raise ValueError(
                f"Invalid data_type '{data_type}'. Must be one of: {sorted(_VALID_DATA_TYPES)}"
            )
        if self._repo.get_by_field_key(
            company_id=company_id, entity_type=entity_type, field_key=field_key
        ):
            raise CustomFieldKeyConflictError(
                message=f"Custom field '{field_key}' already exists for entity type '{entity_type}'.",
                details={"field_key": field_key, "entity_type": entity_type},
            )
        custom_field = CustomFieldDefinition(
            company_id=company_id,
            entity_type=entity_type,
            field_key=field_key,
            field_label=field_label,
            data_type=data_type,
            options=options,
            is_required=is_required,
            sort_order=sort_order,
            placeholder=placeholder,
            created_by=actor_id,
        )
        result = self._repo.create(custom_field)
        logger.info(
            "CustomField created: id=%s key=%s entity=%s company=%s",
            result.id,
            field_key,
            entity_type,
            company_id,
        )
        return result

    def get_by_id(self, company_id: UUID, field_id: UUID) -> CustomFieldDefinition:
        """Return custom field definition by ID or raise CustomFieldNotFoundError."""
        from core.exceptions.base import NotFoundException

        try:
            return self._repo.get_by_id(id=field_id, company_id=company_id)
        except NotFoundException:
            raise CustomFieldNotFoundError(details={"field_id": str(field_id)})

    def list_for_entity(
        self, company_id: UUID, entity_type: str
    ) -> list[CustomFieldDefinition]:
        """Return all custom fields for a given entity type."""
        return self._repo.list_for_entity_type(
            company_id=company_id, entity_type=entity_type
        )

    def update(
        self,
        company_id: UUID,
        field_id: UUID,
        field_label: str | None = None,
        placeholder: str | None = None,
        is_required: bool | None = None,
        sort_order: int | None = None,
    ) -> CustomFieldDefinition:
        """Update custom field definition."""
        cf = self.get_by_id(company_id=company_id, field_id=field_id)
        if field_label is not None:
            cf.field_label = field_label
        if placeholder is not None:
            cf.placeholder = placeholder
        if is_required is not None:
            cf.is_required = is_required
        if sort_order is not None:
            cf.sort_order = sort_order
        return self._repo.update(cf)

    def delete(self, company_id: UUID, field_id: UUID) -> None:
        """Soft-delete a custom field definition."""
        try:
            self._repo.soft_delete(id=field_id, company_id=company_id)
        except Exception:
            raise CustomFieldNotFoundError(details={"field_id": str(field_id)})


# =============================================================================
# AttributeDefinitionService
# =============================================================================


class AttributeDefinitionService:
    """Application service for product attribute definitions."""

    def __init__(self, db: Session, attr_repo: AttributeDefinitionRepository) -> None:
        self.db = db
        self._repo = attr_repo

    def create(
        self,
        company_id: UUID,
        name: str,
        data_type: str,
        options: list[Any] | dict[str, Any] | None = None,
        is_required: bool = False,
        description: str | None = None,
        actor_id: UUID | None = None,
    ) -> AttributeDefinition:
        """Create an attribute definition.

        Raises:
            AttributeNameConflictError: If attribute name already exists.
            ValueError: If data_type is invalid.
        """
        if data_type not in _VALID_ATTR_DATA_TYPES:
            raise ValueError(
                f"Invalid data_type '{data_type}'. Must be one of: {sorted(_VALID_ATTR_DATA_TYPES)}"
            )
        if self._repo.get_by_name(company_id=company_id, name=name):
            raise AttributeNameConflictError(
                message=f"An attribute named '{name}' already exists.",
                details={"name": name},
            )
        attr = AttributeDefinition(
            company_id=company_id,
            name=name,
            data_type=data_type,
            options=options,
            is_required=is_required,
            description=description,
            created_by=actor_id,
        )
        result = self._repo.create(attr)
        logger.info(
            "AttributeDefinition created: id=%s name=%s company=%s",
            result.id,
            name,
            company_id,
        )
        return result

    def get_by_id(self, company_id: UUID, attr_id: UUID) -> AttributeDefinition:
        """Return attribute definition by ID or raise AttributeNotFoundError."""
        from core.exceptions.base import NotFoundException

        try:
            return self._repo.get_by_id(id=attr_id, company_id=company_id)
        except NotFoundException:
            raise AttributeNotFoundError(details={"attr_id": str(attr_id)})

    def list(self, company_id: UUID) -> list[AttributeDefinition]:
        """Return all attribute definitions for the company."""
        return self._repo.list_active(company_id=company_id)

    def update(
        self,
        company_id: UUID,
        attr_id: UUID,
        description: str | None = None,
        is_required: bool | None = None,
        options: builtins.list[Any] | dict[str, Any] | None = None,
    ) -> AttributeDefinition:
        """Update attribute definition."""
        attr = self.get_by_id(company_id=company_id, attr_id=attr_id)
        if description is not None:
            attr.description = description
        if is_required is not None:
            attr.is_required = is_required
        if options is not None:
            attr.options = options
        return self._repo.update(attr)

    def delete(self, company_id: UUID, attr_id: UUID) -> None:
        """Soft-delete an attribute definition."""
        try:
            self._repo.soft_delete(id=attr_id, company_id=company_id)
        except Exception:
            raise AttributeNotFoundError(details={"attr_id": str(attr_id)})


# =============================================================================
# AttributeSetService
# =============================================================================


class AttributeSetService:
    """Application service for attribute set management."""

    def __init__(
        self,
        db: Session,
        attr_set_repo: AttributeSetRepository,
        membership_repo: AttributeSetMembershipRepository,
        attr_repo: AttributeDefinitionRepository,
    ) -> None:
        self.db = db
        self._repo = attr_set_repo
        self._membership_repo = membership_repo
        self._attr_repo = attr_repo

    def create(
        self,
        company_id: UUID,
        name: str,
        scope: str,
        description: str | None = None,
        actor_id: UUID | None = None,
    ) -> AttributeSet:
        """Create an attribute set.

        Raises:
            AttributeSetNameConflictError: If attribute set name already exists.
            ValueError: If scope is invalid.
        """
        if scope not in _VALID_SCOPES:
            raise ValueError(
                f"Invalid scope '{scope}'. Must be one of: {sorted(_VALID_SCOPES)}"
            )
        if self._repo.get_by_name(company_id=company_id, name=name):
            raise AttributeSetNameConflictError(
                message=f"An attribute set named '{name}' already exists.",
                details={"name": name},
            )
        attr_set = AttributeSet(
            company_id=company_id,
            name=name,
            scope=scope,
            description=description,
            created_by=actor_id,
        )
        result = self._repo.create(attr_set)
        logger.info(
            "AttributeSet created: id=%s name=%s company=%s",
            result.id,
            name,
            company_id,
        )
        return result

    def get_by_id(self, company_id: UUID, attr_set_id: UUID) -> AttributeSet:
        """Return attribute set by ID or raise AttributeSetNotFoundError."""
        from core.exceptions.base import NotFoundException

        try:
            return self._repo.get_by_id(id=attr_set_id, company_id=company_id)
        except NotFoundException:
            raise AttributeSetNotFoundError(details={"attr_set_id": str(attr_set_id)})

    def list(self, company_id: UUID) -> list[AttributeSet]:
        """Return all attribute sets for the company."""
        items, _ = self._repo.list(company_id=company_id, limit=1000)
        return items

    def add_attribute(
        self,
        company_id: UUID,
        attr_set_id: UUID,
        attr_definition_id: UUID,
        sort_order: int = 0,
        actor_id: UUID | None = None,
    ) -> AttributeSetMembership:
        """Add an attribute definition to an attribute set.

        Raises:
            AttributeSetNotFoundError: If attribute set does not exist.
            AttributeNotFoundError: If attribute definition does not exist.
        """
        self.get_by_id(company_id=company_id, attr_set_id=attr_set_id)
        from core.exceptions.base import NotFoundException

        try:
            self._attr_repo.get_by_id(id=attr_definition_id, company_id=company_id)
        except NotFoundException:
            raise AttributeNotFoundError(details={"attr_id": str(attr_definition_id)})
        existing = self._membership_repo.get_by_set_and_definition(
            company_id=company_id,
            attribute_set_id=attr_set_id,
            attribute_definition_id=attr_definition_id,
        )
        if existing:
            return existing  # idempotent
        membership = AttributeSetMembership(
            company_id=company_id,
            attribute_set_id=str(attr_set_id),
            attribute_definition_id=str(attr_definition_id),
            sort_order=sort_order,
            created_by=actor_id,
        )
        return self._membership_repo.create(membership)

    def remove_attribute(
        self,
        company_id: UUID,
        attr_set_id: UUID,
        attr_definition_id: UUID,
    ) -> None:
        """Remove an attribute from a set."""
        membership = self._membership_repo.get_by_set_and_definition(
            company_id=company_id,
            attribute_set_id=attr_set_id,
            attribute_definition_id=attr_definition_id,
        )
        if membership is None:
            return  # idempotent
        self._membership_repo.soft_delete(id=membership.id, company_id=company_id)

    def list_attributes(
        self, company_id: UUID, attr_set_id: UUID
    ) -> builtins.list[AttributeSetMembership]:
        """Return all attribute memberships for a set."""
        return self._membership_repo.list_for_set(
            company_id=company_id, attribute_set_id=attr_set_id
        )

    def delete(self, company_id: UUID, attr_set_id: UUID) -> None:
        """Soft-delete an attribute set."""
        try:
            self._repo.soft_delete(id=attr_set_id, company_id=company_id)
        except Exception:
            raise AttributeSetNotFoundError(details={"attr_set_id": str(attr_set_id)})
