"""Unit tests for response schemas.

T137 — StandardResponse, ErrorResponse, PaginatedResponse, PaginationParams.
"""

from datetime import UTC, datetime

from core.schemas.pagination import PaginatedData, PaginatedResponse, PaginationParams
from core.schemas.response import (
    ErrorDetail,
    ErrorResponse,
    ResponseMeta,
    StandardResponse,
)


def _make_meta() -> ResponseMeta:
    return ResponseMeta(request_id="test-request-id", timestamp=datetime.now(UTC))


class TestStandardResponse:
    def test_standard_response_str_serializes_correctly(self) -> None:
        response: StandardResponse[str] = StandardResponse(
            data="hello",
            message="ok",
            meta=_make_meta(),
        )
        d = response.model_dump()
        assert d["data"] == "hello"
        assert d["message"] == "ok"
        assert "meta" in d
        assert d["meta"]["request_id"] == "test-request-id"

    def test_standard_response_generic_with_dict(self) -> None:
        payload = {"id": "123", "name": "test"}
        response: StandardResponse[dict[str, str]] = StandardResponse(
            data=payload,
            message="created",
            meta=_make_meta(),
        )
        assert response.data == payload

    def test_response_meta_has_request_id_and_timestamp(self) -> None:
        meta = _make_meta()
        assert meta.request_id == "test-request-id"
        assert meta.timestamp is not None


class TestErrorResponse:
    def test_error_response_serializes_correctly(self) -> None:
        response = ErrorResponse(
            error=ErrorDetail(
                code="NOT_FOUND",
                message="Resource not found",
                details={},
            )
        )
        d = response.model_dump()
        assert d["error"]["code"] == "NOT_FOUND"
        assert d["error"]["message"] == "Resource not found"
        assert d["error"]["details"] == {}

    def test_error_detail_code_field_present(self) -> None:
        detail = ErrorDetail(code="VALIDATION_ERROR", message="Bad input", details={})
        assert detail.code == "VALIDATION_ERROR"


class TestPaginatedResponse:
    def test_paginated_response_structure(self) -> None:
        items = ["item1", "item2", "item3"]
        data: PaginatedData[str] = PaginatedData(
            items=items,
            total=3,
            page=1,
            page_size=20,
            pages=1,
        )
        response: PaginatedResponse[str] = PaginatedResponse(
            data=data,
            message="ok",
            meta=_make_meta(),
        )
        d = response.model_dump()
        assert d["data"]["total"] == 3
        assert d["data"]["page"] == 1
        assert d["data"]["page_size"] == 20
        assert d["data"]["pages"] == 1
        assert len(d["data"]["items"]) == 3


class TestPaginationParams:
    def test_pagination_params_defaults(self) -> None:
        params = PaginationParams()
        assert params.page == 1
        assert params.page_size == 20

    def test_pagination_params_offset_page_1(self) -> None:
        params = PaginationParams(page=1, page_size=20)
        assert params.offset == 0

    def test_pagination_params_offset_page_2(self) -> None:
        params = PaginationParams(page=2, page_size=20)
        assert params.offset == 20

    def test_pagination_params_custom_page_size(self) -> None:
        params = PaginationParams(page=3, page_size=10)
        assert params.offset == 20
