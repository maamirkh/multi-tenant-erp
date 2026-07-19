"""SQLAlchemy session factory and FastAPI dependency for database sessions.

Usage in a FastAPI route::

    from typing import Annotated
    from fastapi import Depends
    from sqlalchemy.orm import Session
    from core.database.session import get_db

    def my_endpoint(db: Annotated[Session, Depends(get_db)]) -> ...:
        ...

Design decisions:
  - ``autocommit=False``: the application controls transaction boundaries
    explicitly via ``session.commit()`` inside services/repositories.
  - ``autoflush=False``: prevents automatic SQL flushes before queries,
    which could cause confusing behaviour in complex unit-of-work scenarios.
  - The ``finally`` block in ``get_db`` guarantees the session is closed
    even if an exception propagates, returning the connection to the pool.
"""

from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker

from core.database.engine import engine

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a SQLAlchemy ``Session``.

    Yields a session for the duration of the request and closes it in the
    ``finally`` block to guarantee connection pool release regardless of
    whether the request succeeds or raises an exception.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
