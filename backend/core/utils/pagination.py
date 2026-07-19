"""Pagination calculation helpers.

These pure functions are used by ``BaseRepository.list()`` and by routers
that build ``PaginatedResponse`` envelopes.  They contain no I/O and are
trivially unit-testable.
"""

import math


def calculate_pages(total: int, page_size: int) -> int:
    """Return the total number of pages for a result set.

    Returns 0 when *total* is 0 (no results, no pages).

    Args:
        total:     Total number of records matching the query.
        page_size: Number of records per page (must be >= 1).

    Examples::

        calculate_pages(0, 20)    # 0
        calculate_pages(1, 20)    # 1
        calculate_pages(20, 20)   # 1
        calculate_pages(21, 20)   # 2
        calculate_pages(150, 20)  # 8
    """
    if total == 0:
        return 0
    return math.ceil(total / page_size)


def calculate_offset(page: int, page_size: int) -> int:
    """Return the SQL OFFSET value for a 1-indexed page number.

    Args:
        page:      Current page number (1-indexed; page 1 has offset 0).
        page_size: Number of records per page.

    Examples::

        calculate_offset(1, 20)  # 0
        calculate_offset(2, 20)  # 20
        calculate_offset(3, 20)  # 40
    """
    return (page - 1) * page_size
