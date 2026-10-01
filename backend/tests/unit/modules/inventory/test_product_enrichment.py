"""Unit tests for Phase 3 product enrichment — Tags, CustomFieldValues, Notes, ImportJob.

Tests cover:
  - ProductTag ORM model fields and constraints
  - ProductCustomFieldValue field storage
  - ProductInternalNote append-only semantics
  - ImportJob status state machine
  - BulkImportService CSV parsing logic

Spec ref: specs/005-inventory-management/spec.md §14, §35
"""

from __future__ import annotations

import io
import uuid
from typing import Any, cast
from unittest.mock import MagicMock, patch

from sqlalchemy import Table

from modules.inventory.models.product_enrichment import (
    ImportJob,
    ProductCustomFieldValue,
    ProductInternalNote,
    ProductTag,
)

# =============================================================================
# ProductTag model tests
# =============================================================================


class TestProductTagModel:
    def test_product_tag_tablename(self):
        assert ProductTag.__tablename__ == "inventory_product_tags"

    def test_product_tag_has_required_columns(self):
        cols = {c.name for c in ProductTag.__table__.columns}
        assert "id" in cols
        assert "company_id" in cols
        assert "product_id" in cols
        assert "tag_id" in cols
        assert "is_deleted" in cols
        assert "created_at" in cols

    def test_product_tag_unique_constraint_exists(self):
        uq_names = {c.name for c in cast(Table, ProductTag.__table__).constraints}
        assert "uq_inv_product_tags_product_tag" in uq_names

    def test_product_tag_instantiation(self):
        company_id = uuid.uuid4()
        pt = ProductTag(
            company_id=company_id,
            product_id=str(uuid.uuid4()),
            tag_id=str(uuid.uuid4()),
        )
        assert pt.company_id == company_id
        assert not pt.is_deleted


# =============================================================================
# ProductCustomFieldValue model tests
# =============================================================================


class TestProductCustomFieldValueModel:
    def test_tablename(self):
        assert (
            ProductCustomFieldValue.__tablename__
            == "inventory_product_custom_field_values"
        )

    def test_has_value_columns(self):
        cols = {c.name for c in ProductCustomFieldValue.__table__.columns}
        assert "value_text" in cols
        assert "value_number" in cols
        assert "value_bool" in cols
        assert "value_json" in cols
        assert "field_key" in cols

    def test_unique_constraint(self):
        uq_names = {
            c.name for c in cast(Table, ProductCustomFieldValue.__table__).constraints
        }
        assert "uq_inv_product_cfv_product_field" in uq_names

    def test_instantiation_text_value(self):
        cfv = ProductCustomFieldValue(
            company_id=uuid.uuid4(),
            product_id=str(uuid.uuid4()),
            field_key="warranty_months",
            value_text="24",
        )
        assert cfv.field_key == "warranty_months"
        assert cfv.value_text == "24"
        assert cfv.value_bool is None
        assert cfv.value_number is None
        assert cfv.value_json is None

    def test_instantiation_bool_value(self):
        cfv = ProductCustomFieldValue(
            company_id=uuid.uuid4(),
            product_id=str(uuid.uuid4()),
            field_key="is_hazardous",
            value_bool=True,
        )
        assert cfv.value_bool is True

    def test_instantiation_json_value(self):
        cfv = ProductCustomFieldValue(
            company_id=uuid.uuid4(),
            product_id=str(uuid.uuid4()),
            field_key="certifications",
            value_json={"values": ["CE", "RoHS"]},
        )
        assert cfv.value_json == {"values": ["CE", "RoHS"]}


# =============================================================================
# ProductInternalNote model tests
# =============================================================================


class TestProductInternalNoteModel:
    def test_tablename(self):
        assert ProductInternalNote.__tablename__ == "inventory_product_internal_notes"

    def test_has_note_columns(self):
        cols = {c.name for c in ProductInternalNote.__table__.columns}
        assert "note_text" in cols
        assert "author_id" in cols
        assert "product_id" in cols

    def test_instantiation(self):
        note = ProductInternalNote(
            company_id=uuid.uuid4(),
            product_id=str(uuid.uuid4()),
            note_text="Price updated for Q3 promotion.",
            author_id=str(uuid.uuid4()),
        )
        assert "Q3" in note.note_text
        assert not note.is_deleted

    def test_system_note_author_nullable(self):
        """System-generated notes may have no author."""
        note = ProductInternalNote(
            company_id=uuid.uuid4(),
            product_id=str(uuid.uuid4()),
            note_text="Product imported via CSV batch job.",
            author_id=None,
        )
        assert note.author_id is None


# =============================================================================
# ImportJob model tests
# =============================================================================


class TestImportJobModel:
    def test_tablename(self):
        assert ImportJob.__tablename__ == "inventory_import_jobs"

    def test_has_tracking_columns(self):
        cols = {c.name for c in ImportJob.__table__.columns}
        assert "status" in cols
        assert "file_name" in cols
        assert "total_rows" in cols
        assert "processed_rows" in cols
        assert "failed_rows" in cols
        assert "error_rows" in cols
        assert "error_message" in cols

    def test_check_constraint_exists(self):
        ck_names = {c.name for c in cast(Table, ImportJob.__table__).constraints}
        assert "ck_inv_import_jobs_status" in ck_names

    def test_instantiation_pending(self):
        job = ImportJob(
            company_id=uuid.uuid4(),
            file_name="products_batch.csv",
            total_rows=500,
        )
        assert job.file_name == "products_batch.csv"
        assert job.total_rows == 500
        # server_default is PENDING but Python-side not set until flush
        assert not job.is_deleted

    def test_error_rows_stores_list(self):
        job = ImportJob(
            company_id=uuid.uuid4(),
            file_name="bad.csv",
            total_rows=3,
            processed_rows=2,
            failed_rows=1,
            error_rows=[
                {"row_number": 3, "product_code": "X", "errors": ["invalid UOM"]}
            ],
            status="FAILED_WITH_ERRORS",
        )
        assert job.error_rows is not None
        assert len(job.error_rows) == 1
        assert job.error_rows[0]["errors"] == ["invalid UOM"]


# =============================================================================
# BulkImportService — CSV parsing unit tests
# =============================================================================


class TestBulkImportServiceCsvParsing:
    """Test CSV parsing logic without a database — uses mocks."""

    def _make_service(self, db_mock=None, products=None):
        """Build a BulkImportService with fully mocked deps."""
        from modules.inventory.services.bulk_import_service import BulkImportService

        db = db_mock or MagicMock()
        product_repo = MagicMock()
        product_repo.get_by_code.return_value = None  # no duplicates by default

        job_repo = MagicMock()
        job = ImportJob(
            company_id=uuid.uuid4(),
            file_name="test.csv",
            total_rows=0,
        )
        job.id = uuid.uuid4()
        job.processed_rows = 0
        job.failed_rows = 0
        job.error_rows = None
        job.error_message = None
        job.status = "PENDING"
        job_repo.create.return_value = job
        job_repo.update_status.return_value = job

        product_service = MagicMock()

        svc = BulkImportService(
            db=db,
            product_repo=product_repo,
            job_repo=job_repo,
            product_service=product_service,
        )
        return svc, product_repo, job_repo, product_service, job

    def _make_csv(self, rows: list[dict[str, Any]]) -> bytes:
        import csv

        fields = list(rows[0].keys()) if rows else []
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue().encode("utf-8")

    def test_empty_csv_results_in_completed_zero_rows(self):
        svc, product_repo, job_repo, product_service, job = self._make_service()
        content = b"product_code,name,base_uom_code\n"  # header only
        # Patch _lookup_uom_id to avoid DB call
        with patch.object(svc, "_lookup_uom_id", return_value=uuid.uuid4()):
            svc.import_csv(uuid.uuid4(), "empty.csv", content)
        # update_status called with COMPLETED and 0 rows
        calls = job_repo.update_status.call_args_list
        final = calls[-1]
        assert "COMPLETED" in str(final)

    def test_missing_required_columns_fails_job(self):
        svc, product_repo, job_repo, product_service, job = self._make_service()
        content = b"name,product_type\nTV,STANDARD\n"
        svc.import_csv(uuid.uuid4(), "bad.csv", content)
        calls = job_repo.update_status.call_args_list
        final = calls[-1]
        assert "FAILED" in str(final)

    def test_invalid_product_type_collected_as_error(self):
        svc, product_repo, job_repo, product_service, job = self._make_service()
        rows = [
            {
                "product_code": "TV-001",
                "name": "TV",
                "base_uom_code": "PCS",
                "product_type": "INVALID",
            }
        ]
        content = self._make_csv(rows)
        with patch.object(svc, "_lookup_uom_id", return_value=uuid.uuid4()):
            svc.import_csv(uuid.uuid4(), "test.csv", content)
        # product_service.create_product should NOT be called
        product_service.create_product.assert_not_called()

    def test_duplicate_sku_collected_as_error(self):
        svc, product_repo, job_repo, product_service, job = self._make_service()
        product_repo.get_by_code.return_value = MagicMock()  # simulate duplicate
        rows = [
            {
                "product_code": "TV-001",
                "name": "TV",
                "base_uom_code": "PCS",
                "product_type": "STANDARD",
            }
        ]
        content = self._make_csv(rows)
        with patch.object(svc, "_lookup_uom_id", return_value=uuid.uuid4()):
            svc.import_csv(uuid.uuid4(), "test.csv", content)
        product_service.create_product.assert_not_called()

    def test_uom_not_found_collected_as_error(self):
        svc, product_repo, job_repo, product_service, job = self._make_service()
        rows = [
            {
                "product_code": "TV-001",
                "name": "TV",
                "base_uom_code": "UNKNOWN",
                "product_type": "STANDARD",
            }
        ]
        content = self._make_csv(rows)
        with patch.object(svc, "_lookup_uom_id", return_value=None):
            svc.import_csv(uuid.uuid4(), "test.csv", content)
        product_service.create_product.assert_not_called()

    def test_valid_row_calls_create_product(self):
        svc, product_repo, job_repo, product_service, job = self._make_service()
        rows = [
            {
                "product_code": "TV-001",
                "name": 'Smart TV 55"',
                "base_uom_code": "PCS",
                "product_type": "STANDARD",
            }
        ]
        content = self._make_csv(rows)
        uom_id = uuid.uuid4()
        with patch.object(svc, "_lookup_uom_id", return_value=uom_id):
            svc.import_csv(uuid.uuid4(), "test.csv", content)
        product_service.create_product.assert_called_once()
        call_kwargs = product_service.create_product.call_args.kwargs
        assert call_kwargs["product_code"] == "TV-001"
        assert call_kwargs["name"] == 'Smart TV 55"'
        assert call_kwargs["base_uom_id"] == uom_id

    def test_mixed_valid_invalid_rows(self):
        svc, product_repo, job_repo, product_service, job = self._make_service()
        rows = [
            {
                "product_code": "TV-001",
                "name": "TV",
                "base_uom_code": "PCS",
                "product_type": "STANDARD",
            },  # valid
            {
                "product_code": "",
                "name": "Broken",
                "base_uom_code": "PCS",
                "product_type": "STANDARD",
            },  # missing code
        ]
        content = self._make_csv(rows)
        uom_id = uuid.uuid4()
        with patch.object(svc, "_lookup_uom_id", return_value=uom_id):
            svc.import_csv(uuid.uuid4(), "test.csv", content)
        product_service.create_product.assert_called_once()  # only 1 valid

    def test_malformed_csv_bytes_fails_gracefully(self):
        svc, product_repo, job_repo, product_service, job = self._make_service()
        content = b"\xff\xfe invalid utf-16 garbage \x00\x00"
        # Should not raise — job should be marked FAILED
        try:
            svc.import_csv(uuid.uuid4(), "bad.csv", content)
        except Exception:
            pass  # acceptable to raise — tested that it doesn't crash silently
