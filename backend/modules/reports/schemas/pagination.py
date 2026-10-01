"""``CursorPage[T]`` — the one cursor-paginated exception to the platform's
otherwise-universal offset pagination (``accounting.gl`` only, plan.md
§19). Never used for any other report."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

RowT = TypeVar("RowT")


class CursorPage(BaseModel, Generic[RowT]):  # noqa: UP046
    items: list[RowT]
    has_more: bool
    next_cursor: str | None = None
