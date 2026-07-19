"""Generic base service for all DevSphere ERP modules.

**Service layer contract**

Services sit between FastAPI routers and repositories.  They:

- Orchestrate one or more repository calls within a single unit-of-work.
- Hold all business rules and application logic.
- Keep routers thin (routers only parse HTTP concerns and delegate here).
- Are injected with a ``Session`` by the FastAPI ``get_db`` dependency; they
  pass that same session to every repository they construct so all operations
  share a single transaction.

**What services must NOT do**

- Contain SQL queries or direct ORM calls — that is the repository's job.
- Return ORM model instances to routers — convert to Pydantic schemas first.
- Handle HTTP request/response concerns.

**Extending BaseService**::

    class ProductService(BaseService):
        def __init__(self, db: Session) -> None:
            super().__init__(db)
            self.products = ProductRepository(db=db, model=Product)

        def create_product(
            self, payload: ProductCreate, company_id: UUID
        ) -> ProductOut:
            # business validation lives here, not in the repository
            existing = self.products.get_by_id_or_none(payload.sku, company_id)
            if existing:
                raise ConflictException("SKU already exists.")
            entity = Product(company_id=company_id, **payload.model_dump())
            saved = self.products.create(entity)
            return ProductOut.model_validate(saved)
"""

from sqlalchemy.orm import Session


class BaseService:
    """Thin base class for all application services.

    Stores the injected ``Session`` and makes it available to concrete
    subclasses.  No business logic lives in this base class.

    Args:
        db: SQLAlchemy ``Session`` injected by the FastAPI ``get_db``
            dependency.  The session is shared across all repositories
            constructed by the concrete service so that all operations
            within a single request participate in the same transaction.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
