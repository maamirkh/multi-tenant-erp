"""SQLAlchemy declarative base for all ORM models.

All ORM model classes across every ERP module MUST inherit from ``Base``.
Using a single shared ``Base`` ensures that ``Base.metadata`` carries the
complete schema graph, which Alembic needs for autogenerate support.

Import rules:
  - This module must NOT import from ``engine``, ``session``, or any model.
  - Models import ``Base`` from here.
  - ``migrations/env.py`` imports ``Base.metadata`` from here.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Root declarative base.

    Inheriting from SQLAlchemy's ``DeclarativeBase`` (ORM 2.x style) rather
    than calling ``declarative_base()`` gives full type-safety and IDE support
    for mapped columns.
    """
