"""Company logo upload and validation service.

MIME type detection uses raw magic-byte inspection of the file header —
no external ``python-magic`` library required.  The mapping covers all
formats permitted by spec.md §6.3 (PNG, JPEG, WebP, SVG, GIF).

SVG content is also inspected for embedded ``<script>`` or JavaScript
event-handler attributes that would constitute a stored-XSS vector.

Spec reference: §6.3 Logo Upload, BR-027.
"""

from __future__ import annotations

import logging
import re
from io import BytesIO
from typing import BinaryIO, Protocol
from uuid import UUID, uuid4

from modules.companies.exceptions import (
    LogoInvalidContentError,
    LogoInvalidFormatError,
    LogoTooLargeError,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MIME detection helpers
# ---------------------------------------------------------------------------

# Allowed MIME types and their canonical extension for key naming
_ALLOWED_MIME_TYPES: frozenset[str] = frozenset(
    {"image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml"}
)

# Magic byte signatures → MIME type
_MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    # WebP: "RIFF" at 0..3, "WEBP" at 8..11
]

# Regex patterns that indicate dangerous SVG content
# ---------------------------------------------------------------------------
# Storage protocol — avoids a direct boto3 import at module load time
# ---------------------------------------------------------------------------


class _StorageProtocol(Protocol):
    """Structural subtype of ``StorageClient`` accepted by ``CompanyLogoService``."""

    def upload(self, file: BinaryIO, key: str) -> str: ...  # noqa: E704

    def delete(self, key: str) -> None: ...  # noqa: E704

    def get_url(self, key: str) -> str: ...  # noqa: E704


# ---------------------------------------------------------------------------

_SVG_DANGEROUS_PATTERNS: list[re.Pattern[bytes]] = [
    re.compile(rb"<script", re.IGNORECASE),
    re.compile(rb"\bon\w+\s*=", re.IGNORECASE),  # event handlers: onclick=, onerror=, …
    re.compile(rb"javascript:", re.IGNORECASE),
    re.compile(rb"<iframe", re.IGNORECASE),
    re.compile(rb"<embed", re.IGNORECASE),
    re.compile(rb"<object", re.IGNORECASE),
]


def _detect_mime(file_bytes: bytes) -> str | None:
    """Return the MIME type detected from ``file_bytes`` header, or ``None``."""
    if len(file_bytes) >= 12:
        # WebP: RIFF????WEBP
        if file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP":
            return "image/webp"

    for signature, mime_type in _MAGIC_SIGNATURES:
        if file_bytes[: len(signature)] == signature:
            return mime_type

    # SVG: XML text starting with optional BOM / <?xml or <svg
    if _looks_like_svg(file_bytes):
        return "image/svg+xml"

    return None


def _looks_like_svg(file_bytes: bytes) -> bool:
    """Return ``True`` if the bytes look like an SVG XML document."""
    sample = file_bytes[:512]
    # Strip UTF-8 BOM if present
    if sample.startswith(b"\xef\xbb\xbf"):
        sample = sample[3:]
    # Must start with XML declaration or <svg tag
    stripped = sample.lstrip()
    return stripped.startswith(b"<?xml") or stripped.startswith(b"<svg")


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class CompanyLogoService:
    """Validates, uploads, and manages company logo files.

    Args:
        storage: Any object implementing the ``_StorageProtocol`` (S3/MinIO or mock).
            The concrete ``S3StorageClient`` from ``core.storage.s3_client`` satisfies
            this protocol; inject it via FastAPI DI in Phase 8.
        max_bytes: Maximum allowed file size in bytes (from ``Settings.COMPANY_LOGO_MAX_BYTES``).
        logo_folder: S3 key prefix for logo objects (default: ``"logos"``).
    """

    def __init__(
        self,
        storage: _StorageProtocol,
        max_bytes: int,
        logo_folder: str = "logos",
    ) -> None:
        self._storage = storage
        self._max_bytes = max_bytes
        self._logo_folder = logo_folder

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_file(self, file_bytes: bytes, filename: str) -> str:
        """Validate logo file size, format, and content.

        Performs three checks in order:
        1. File size ≤ ``max_bytes`` → raises :exc:`LogoTooLargeError`.
        2. MIME type from magic bytes in ``_ALLOWED_MIME_TYPES`` → raises
           :exc:`LogoInvalidFormatError`.
        3. For SVG files, no dangerous script/event content → raises
           :exc:`LogoInvalidContentError`.

        Args:
            file_bytes: Raw file content read into memory.
            filename: Original filename (used only for logging; MIME is
                detected from bytes, not extension).

        Returns:
            The detected MIME type string (e.g. ``"image/png"``).

        Raises:
            LogoTooLargeError: File exceeds the configured size limit.
            LogoInvalidFormatError: MIME type not in the allowed set.
            LogoInvalidContentError: SVG contains unsafe embedded content.
        """
        if len(file_bytes) > self._max_bytes:
            raise LogoTooLargeError(
                details={
                    "max_bytes": self._max_bytes,
                    "received_bytes": len(file_bytes),
                }
            )

        detected_mime = _detect_mime(file_bytes)

        if detected_mime is None or detected_mime not in _ALLOWED_MIME_TYPES:
            raise LogoInvalidFormatError(
                details={
                    "filename": filename,
                    "detected_mime": detected_mime,
                    "allowed_types": sorted(_ALLOWED_MIME_TYPES),
                }
            )

        if detected_mime == "image/svg+xml":
            self._validate_svg_content(file_bytes)

        return detected_mime

    def upload(self, file_bytes: bytes, company_id: UUID, mime_type: str) -> str:
        """Upload logo bytes to object storage and return the public URL.

        Generates a UUID-based key to avoid collisions and prevent
        enumeration.  The MIME type is encoded in the key extension for
        correct ``Content-Type`` headers when served from S3.

        Args:
            file_bytes: Validated logo content.
            company_id: Owning company UUID (used as folder segment in key).
            mime_type: Validated MIME type string.

        Returns:
            Public URL of the uploaded object.
        """
        ext = self._mime_to_ext(mime_type)
        key = f"{self._logo_folder}/{company_id}/{uuid4()}{ext}"
        file_obj = BytesIO(file_bytes)
        return self._storage.upload(file_obj, key)

    def schedule_previous_cleanup(self, previous_url: str | None) -> None:
        """Log the previous logo URL for background cleanup.

        The actual deletion of the old logo from object storage is deferred
        to a background job (future epic) to allow CDN cache propagation.
        This stub records the URL so the background process can find it.

        Args:
            previous_url: The previous logo URL to be cleaned up, or
                ``None`` if there was no previous logo.
        """
        if previous_url:
            logger.info(
                "Logo replacement scheduled for cleanup",
                extra={"previous_logo_url": previous_url},
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_svg_content(self, file_bytes: bytes) -> None:
        """Raise :exc:`LogoInvalidContentError` if the SVG contains dangerous content."""
        for pattern in _SVG_DANGEROUS_PATTERNS:
            if pattern.search(file_bytes):
                raise LogoInvalidContentError(
                    details={
                        "reason": "SVG contains potentially unsafe embedded content."
                    }
                )

    @staticmethod
    def _mime_to_ext(mime_type: str) -> str:
        _map = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "image/svg+xml": ".svg",
        }
        return _map.get(mime_type, "")
