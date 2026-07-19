"""Unit tests for core utility functions.

T139 — generate_uuid, is_valid_uuid, utcnow, format_iso, ensure_utc,
       calculate_pages, calculate_offset.
"""

from datetime import UTC, datetime, timezone
from uuid import UUID

from core.utils.datetime import ensure_utc, format_iso, utcnow
from core.utils.pagination import calculate_offset, calculate_pages
from core.utils.uuid import generate_uuid, is_valid_uuid


class TestGenerateUuid:
    def test_returns_uuid_instance(self) -> None:
        result = generate_uuid()
        assert isinstance(result, UUID)

    def test_each_call_returns_unique_value(self) -> None:
        a = generate_uuid()
        b = generate_uuid()
        assert a != b

    def test_version_is_4(self) -> None:
        result = generate_uuid()
        assert result.version == 4


class TestIsValidUuid:
    def test_valid_uuid_string_returns_true(self) -> None:
        uid = str(generate_uuid())
        assert is_valid_uuid(uid) is True

    def test_invalid_string_returns_false(self) -> None:
        assert is_valid_uuid("not-a-uuid") is False

    def test_empty_string_returns_false(self) -> None:
        assert is_valid_uuid("") is False

    def test_nil_uuid_returns_true(self) -> None:
        assert is_valid_uuid("00000000-0000-0000-0000-000000000000") is True

    def test_uppercase_uuid_returns_true(self) -> None:
        uid = str(generate_uuid()).upper()
        assert is_valid_uuid(uid) is True


class TestUtcnow:
    def test_returns_datetime(self) -> None:
        result = utcnow()
        assert isinstance(result, datetime)

    def test_is_timezone_aware(self) -> None:
        result = utcnow()
        assert result.tzinfo is not None

    def test_timezone_is_utc(self) -> None:
        result = utcnow()
        assert result.utcoffset().total_seconds() == 0  # type: ignore[union-attr]


class TestFormatIso:
    def test_returns_string(self) -> None:
        result = format_iso(utcnow())
        assert isinstance(result, str)

    def test_output_is_valid_iso8601(self) -> None:
        dt = utcnow()
        iso_str = format_iso(dt)
        parsed = datetime.fromisoformat(iso_str)
        assert parsed is not None

    def test_roundtrip_preserves_value(self) -> None:
        dt = utcnow()
        iso_str = format_iso(dt)
        parsed = datetime.fromisoformat(iso_str)
        assert parsed == dt


class TestEnsureUtc:
    def test_naive_datetime_gets_utc_tzinfo(self) -> None:
        naive = datetime(2026, 1, 1, 12, 0, 0)
        result = ensure_utc(naive)
        assert result.tzinfo == UTC

    def test_utc_aware_datetime_unchanged(self) -> None:
        aware = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        result = ensure_utc(aware)
        assert result == aware

    def test_non_utc_aware_datetime_converted(self) -> None:
        est = timezone(offset=__import__("datetime").timedelta(hours=-5))
        aware_est = datetime(2026, 1, 1, 12, 0, 0, tzinfo=est)
        result = ensure_utc(aware_est)
        assert result.utcoffset().total_seconds() == 0  # type: ignore[union-attr]


class TestCalculatePages:
    def test_zero_total_returns_zero_pages(self) -> None:
        assert calculate_pages(0, 20) == 0

    def test_total_equal_to_page_size(self) -> None:
        assert calculate_pages(20, 20) == 1

    def test_total_less_than_page_size(self) -> None:
        assert calculate_pages(5, 20) == 1

    def test_total_exceeds_page_size(self) -> None:
        assert calculate_pages(21, 20) == 2

    def test_large_total(self) -> None:
        assert calculate_pages(150, 20) == 8

    def test_single_item_page_size_one(self) -> None:
        assert calculate_pages(1, 1) == 1


class TestCalculateOffset:
    def test_page_1_has_offset_0(self) -> None:
        assert calculate_offset(1, 20) == 0

    def test_page_2_has_offset_equal_to_page_size(self) -> None:
        assert calculate_offset(2, 20) == 20

    def test_page_3_offset(self) -> None:
        assert calculate_offset(3, 20) == 40

    def test_custom_page_size(self) -> None:
        assert calculate_offset(3, 10) == 20

    def test_page_1_any_page_size_is_zero(self) -> None:
        assert calculate_offset(1, 100) == 0
