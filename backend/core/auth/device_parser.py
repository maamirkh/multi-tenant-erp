"""User-Agent device parsing utilities.

Parses raw ``User-Agent`` header strings into structured device information
for session tracking and audit purposes.  No external dependencies are
required — detection is handled with the standard library's ``re`` module.

Usage::

    from core.auth.device_parser import parse_user_agent, device_info_to_dict

    info = parse_user_agent(request.headers.get("user-agent"))
    # DeviceInfo(browser='Chrome', browser_version='120.0', os='Windows', ...)
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    """Parsed device information extracted from a User-Agent string.

    All string fields are ``None`` when they cannot be determined.
    ``device_type`` is one of ``"desktop"``, ``"mobile"``, ``"tablet"``,
    ``"bot"``, or ``"unknown"``.
    """

    browser: str | None
    browser_version: str | None
    os: str | None
    os_version: str | None
    device_type: str
    raw_user_agent: str | None


# ---------------------------------------------------------------------------
# Detection patterns (most-specific first)
# ---------------------------------------------------------------------------

_BOT_PATTERN = re.compile(
    r"(bot|crawler|spider|scraper|slurp|facebookexternalhit|WhatsApp"
    r"|Googlebot|bingbot|yandex|DuckDuckBot|Baiduspider)",
    re.IGNORECASE,
)

# Browser patterns in precedence order.  Edge must come before Chrome because
# Edge's UA string contains "Chrome/" too.
_BROWSER_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"Edg(?:e)?/([\d.]+)", re.IGNORECASE), "Edge"),
    (re.compile(r"OPR/([\d.]+)", re.IGNORECASE), "Opera"),
    (re.compile(r"Chrome/([\d.]+)", re.IGNORECASE), "Chrome"),
    (re.compile(r"Firefox/([\d.]+)", re.IGNORECASE), "Firefox"),
    (re.compile(r"Version/([\d.]+).*Safari", re.IGNORECASE), "Safari"),
    (re.compile(r"MSIE\s([\d.]+)", re.IGNORECASE), "IE"),
    (re.compile(r"Trident/.*rv:([\d.]+)", re.IGNORECASE), "IE"),
]

# OS patterns — Android/iOS must precede Linux/Windows generics.
_OS_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"Android ([\d.]+)", re.IGNORECASE), "Android"),
    (re.compile(r"iPhone OS ([\d_]+)", re.IGNORECASE), "iOS"),
    (re.compile(r"iPad.*OS ([\d_]+)", re.IGNORECASE), "iPadOS"),
    (re.compile(r"Windows NT ([\d.]+)", re.IGNORECASE), "Windows"),
    (re.compile(r"Mac OS X ([\d_.]+)", re.IGNORECASE), "macOS"),
    (re.compile(r"CrOS\s\S+\s([\d.]+)", re.IGNORECASE), "ChromeOS"),
    (re.compile(r"Linux", re.IGNORECASE), "Linux"),
]

_TABLET_PATTERN = re.compile(r"(iPad|Tablet)", re.IGNORECASE)
_MOBILE_PATTERN = re.compile(r"(Mobile|iPhone|Android(?!.*Tablet))", re.IGNORECASE)


def parse_user_agent(user_agent: str | None) -> DeviceInfo:
    """Parse a raw User-Agent string into structured :class:`DeviceInfo`.

    Args:
        user_agent: Raw ``User-Agent`` header value, or ``None``.

    Returns:
        A :class:`DeviceInfo` with best-effort parsed fields.
        Unknown fields are ``None``; ``device_type`` defaults to ``"unknown"``.
    """
    if not user_agent:
        return DeviceInfo(
            browser=None,
            browser_version=None,
            os=None,
            os_version=None,
            device_type="unknown",
            raw_user_agent=user_agent,
        )

    ua = user_agent.strip()

    # Bots / crawlers take priority.
    if _BOT_PATTERN.search(ua):
        return DeviceInfo(
            browser=None,
            browser_version=None,
            os=None,
            os_version=None,
            device_type="bot",
            raw_user_agent=ua,
        )

    # Browser detection.
    browser: str | None = None
    browser_version: str | None = None
    for pattern, name in _BROWSER_PATTERNS:
        m = pattern.search(ua)
        if m:
            browser = name
            browser_version = m.group(1)
            break

    # OS detection.
    os_name: str | None = None
    os_version: str | None = None
    for pattern, name in _OS_PATTERNS:
        m = pattern.search(ua)
        if m:
            os_name = name
            # group(1) may not exist for the bare "Linux" pattern.
            try:
                os_version = m.group(1).replace("_", ".")
            except IndexError:
                os_version = None
            break

    # Device type.
    if _TABLET_PATTERN.search(ua):
        device_type = "tablet"
    elif _MOBILE_PATTERN.search(ua):
        device_type = "mobile"
    else:
        device_type = "desktop"

    return DeviceInfo(
        browser=browser,
        browser_version=browser_version,
        os=os_name,
        os_version=os_version,
        device_type=device_type,
        raw_user_agent=ua,
    )


def device_info_to_dict(info: DeviceInfo) -> dict[str, str | None]:
    """Serialise :class:`DeviceInfo` to a plain dict for audit log metadata.

    The ``raw_user_agent`` field is intentionally excluded because it can be
    very long and is already stored in the audit log's ``user_agent`` column.
    """
    return {
        "browser": info.browser,
        "browser_version": info.browser_version,
        "os": info.os,
        "os_version": info.os_version,
        "device_type": info.device_type,
    }
