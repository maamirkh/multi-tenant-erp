"""Unit tests for CompanyLogoService — logo validation and upload.

All tests are pure unit tests; the S3 storage client is mocked.
MIME detection is performed via raw magic bytes, matching production
behaviour exactly (no python-magic dependency required).
"""

from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from modules.companies.exceptions import (
    LogoInvalidContentError,
    LogoInvalidFormatError,
    LogoTooLargeError,
)
from modules.companies.services.company_logo_service import (
    CompanyLogoService,
    _detect_mime,
)

# ---------------------------------------------------------------------------
# Sample magic bytes for test images
# ---------------------------------------------------------------------------

# Minimal valid PNG: 8-byte signature + IHDR chunk
_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

# Minimal valid JPEG: SOI marker
_JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 100

# Minimal GIF89a
_GIF_BYTES = b"GIF89a" + b"\x00" * 100

# WebP: RIFF....WEBP
_WEBP_BYTES = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 100

# Valid SVG (no dangerous content)
_SVG_SAFE = b"<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100'><circle r='50'/></svg>"

# SVG with embedded script (dangerous)
_SVG_XSS_SCRIPT = b"<svg><script>alert(1)</script></svg>"

# SVG with onclick event handler
_SVG_XSS_EVENT = b"<svg><rect onclick='alert(1)'/></svg>"

# SVG with javascript: URI
_SVG_XSS_JS_URI = b"<svg><a href='javascript:void(0)'>x</a></svg>"

# PNG bytes renamed as .exe (content still PNG, extension lies)
_PNG_DISGUISED_AS_EXE = _PNG_BYTES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_service(max_bytes: int = 2_097_152) -> tuple[CompanyLogoService, MagicMock]:
    storage = MagicMock()
    storage.upload.return_value = "https://bucket.s3.amazonaws.com/logos/test.png"
    service = CompanyLogoService(storage=storage, max_bytes=max_bytes)
    return service, storage


# ---------------------------------------------------------------------------
# _detect_mime helper
# ---------------------------------------------------------------------------


class TestDetectMime:
    def test_detects_png(self) -> None:
        assert _detect_mime(_PNG_BYTES) == "image/png"

    def test_detects_jpeg(self) -> None:
        assert _detect_mime(_JPEG_BYTES) == "image/jpeg"

    def test_detects_gif(self) -> None:
        assert _detect_mime(_GIF_BYTES) == "image/gif"

    def test_detects_webp(self) -> None:
        assert _detect_mime(_WEBP_BYTES) == "image/webp"

    def test_detects_svg(self) -> None:
        assert _detect_mime(_SVG_SAFE) == "image/svg+xml"

    def test_unknown_returns_none(self) -> None:
        assert _detect_mime(b"\x00\x01\x02\x03") is None

    def test_png_disguised_as_exe_detected_as_png(self) -> None:
        # Magic bytes win over filename — PNG signature is present
        assert _detect_mime(_PNG_DISGUISED_AS_EXE) == "image/png"


# ---------------------------------------------------------------------------
# validate_file — size check
# ---------------------------------------------------------------------------


class TestValidateFileSize:
    def test_file_within_limit_passes(self) -> None:
        service, _ = _make_service(max_bytes=1000)
        mime = service.validate_file(_PNG_BYTES[:500], "logo.png")
        assert mime == "image/png"

    def test_file_at_exact_limit_passes(self) -> None:
        service, _ = _make_service(max_bytes=len(_PNG_BYTES))
        mime = service.validate_file(_PNG_BYTES, "logo.png")
        assert mime == "image/png"

    def test_file_exceeding_limit_raises_too_large(self) -> None:
        service, _ = _make_service(max_bytes=10)
        with pytest.raises(LogoTooLargeError):
            service.validate_file(_PNG_BYTES, "logo.png")

    def test_too_large_error_includes_details(self) -> None:
        service, _ = _make_service(max_bytes=10)
        with pytest.raises(LogoTooLargeError) as exc_info:
            service.validate_file(_PNG_BYTES, "logo.png")
        assert exc_info.value.details["max_bytes"] == 10


# ---------------------------------------------------------------------------
# validate_file — format check
# ---------------------------------------------------------------------------


class TestValidateFileFormat:
    def test_png_passes(self) -> None:
        service, _ = _make_service()
        assert service.validate_file(_PNG_BYTES, "logo.png") == "image/png"

    def test_jpeg_passes(self) -> None:
        service, _ = _make_service()
        assert service.validate_file(_JPEG_BYTES, "photo.jpg") == "image/jpeg"

    def test_gif_passes(self) -> None:
        service, _ = _make_service()
        assert service.validate_file(_GIF_BYTES, "anim.gif") == "image/gif"

    def test_webp_passes(self) -> None:
        service, _ = _make_service()
        assert service.validate_file(_WEBP_BYTES, "logo.webp") == "image/webp"

    def test_svg_safe_passes(self) -> None:
        service, _ = _make_service()
        assert service.validate_file(_SVG_SAFE, "icon.svg") == "image/svg+xml"

    def test_unsupported_type_raises_invalid_format(self) -> None:
        service, _ = _make_service()
        with pytest.raises(LogoInvalidFormatError):
            service.validate_file(b"\x00\x01\x02\x03" + b"\x00" * 100, "unknown.bin")

    def test_png_renamed_exe_detected_as_png(self) -> None:
        service, _ = _make_service()
        # Extension says .exe but magic bytes say PNG
        assert (
            service.validate_file(_PNG_DISGUISED_AS_EXE, "malware.exe") == "image/png"
        )


# ---------------------------------------------------------------------------
# validate_file — SVG content safety
# ---------------------------------------------------------------------------


class TestValidateSvgContent:
    def test_svg_with_script_tag_raises_invalid_content(self) -> None:
        service, _ = _make_service()
        with pytest.raises(LogoInvalidContentError):
            service.validate_file(_SVG_XSS_SCRIPT, "evil.svg")

    def test_svg_with_event_handler_raises_invalid_content(self) -> None:
        service, _ = _make_service()
        with pytest.raises(LogoInvalidContentError):
            service.validate_file(_SVG_XSS_EVENT, "bad.svg")

    def test_svg_with_javascript_uri_raises_invalid_content(self) -> None:
        service, _ = _make_service()
        with pytest.raises(LogoInvalidContentError):
            service.validate_file(_SVG_XSS_JS_URI, "bad.svg")


# ---------------------------------------------------------------------------
# upload
# ---------------------------------------------------------------------------


class TestUpload:
    def test_upload_returns_url(self) -> None:
        service, storage = _make_service()
        url = service.upload(_PNG_BYTES, company_id=uuid4(), mime_type="image/png")
        assert url == "https://bucket.s3.amazonaws.com/logos/test.png"

    def test_upload_calls_storage_with_file_obj(self) -> None:
        service, storage = _make_service()
        company_id = uuid4()
        service.upload(_PNG_BYTES, company_id=company_id, mime_type="image/png")

        storage.upload.assert_called_once()
        file_arg, key_arg = storage.upload.call_args[0]
        assert isinstance(file_arg, BytesIO)
        assert f"{company_id}" in key_arg
        assert key_arg.endswith(".png")

    def test_upload_svg_uses_svg_extension(self) -> None:
        service, storage = _make_service()
        service.upload(_SVG_SAFE, company_id=uuid4(), mime_type="image/svg+xml")

        _, key_arg = storage.upload.call_args[0]
        assert key_arg.endswith(".svg")


# ---------------------------------------------------------------------------
# schedule_previous_cleanup
# ---------------------------------------------------------------------------


class TestSchedulePreviousCleanup:
    def test_cleanup_with_url_does_not_error(self) -> None:
        service, _ = _make_service()
        service.schedule_previous_cleanup("https://bucket/old-logo.png")

    def test_cleanup_with_none_does_not_error(self) -> None:
        service, _ = _make_service()
        service.schedule_previous_cleanup(None)
