"""FastAPI application factory for DevSphere ERP backend."""

import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from core.config.settings import Settings, get_settings
from core.exceptions.base import ApplicationException
from core.exceptions.handler import (
    application_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from core.logging.setup import configure_logging
from core.middleware.auth_hook import AuthHookMiddleware
from core.middleware.request_id import RequestIDMiddleware
from core.middleware.security_headers import SecurityHeadersMiddleware
from core.migrations import run_migrations

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application instance.

    Initialisation order is significant:
    1. Load settings
    2. Configure logging  (must be first — all subsequent steps are observable)
    3. Create FastAPI instance
    4. Store settings on app.state
    5. Register exception handlers          ← Phase 4
    6. Register middleware                  ← Phase 6
    7. Include routers                      ← Phase 6

    Middleware pipeline (outermost → innermost):
        CORSMiddleware → RequestIDMiddleware → AuthHookMiddleware → Route

    The function accepts an optional Settings instance to allow tests to inject
    test-specific configuration without touching the process environment.
    """
    if settings is None:
        settings = get_settings()
    # working
    # Step 2: configure logging before anything else.
    configure_logging(settings)

    app = FastAPI(
        title="DevSphere ERP API",
        description="Foundation Platform API — DevSphere ERP",
        version=settings.API_VERSION,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
    )

    # Step 4: store settings on app state so handlers can access them.
    app.state.settings = settings

    # Attach the SlowAPI limiter instance so SlowAPIMiddleware can find it.
    from modules.auth.router import limiter as auth_limiter

    app.state.limiter = auth_limiter

    # Step 5: register exception handlers.
    # Order matters: more-specific handlers are registered first; the
    # catch-all Exception handler must be last.
    # Handlers accept specific subclass exc types at runtime; mypy requires
    # the base Exception signature, so we suppress the contravariance error.
    app.add_exception_handler(ApplicationException, application_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Step 6: register middleware.
    # add_middleware() builds the pipeline in LIFO order — the last call
    # registered is the outermost (first to process the request).
    #
    # Desired pipeline: CORS → SecurityHeaders → RequestID → AuthHook → SlowAPI → Route
    # Registration order (reverse of desired):
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(AuthHookMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # Step 7: include routers.
    _register_routers(app)

    # Lifecycle events.
    @app.on_event("startup")
    async def on_startup() -> None:
        _validate_auth_configuration(settings)

        # Run database migrations before accepting traffic.
        run_migrations()

        logger.info(
            "Application started",
            extra={
                "environment": settings.ENVIRONMENT,
                "version": settings.API_VERSION,
                "debug": settings.DEBUG,
            },
        )

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        logger.info(
            "Application shutting down",
            extra={
                "environment": settings.ENVIRONMENT,
                "version": settings.API_VERSION,
            },
        )

    return app


def _register_routers(app: FastAPI) -> None:
    """Register all API routers.

    Versioned routers are mounted under /api/<version> so that non-breaking
    evolution is possible without changes to existing consumers.
    """
    from api.v1.router import router as api_v1_router

    # Root endpoint — API metadata / landing page.
    @app.get("/", tags=["root"], summary="API root")
    async def root() -> dict[str, str]:
        """Return basic API metadata."""
        settings: Settings = app.state.settings
        return {
            "name": "DevSphere ERP API",
            "version": settings.API_VERSION,
            "environment": settings.ENVIRONMENT,
            "docs": "/docs" if settings.DEBUG else "disabled",
        }

    # v1 API
    app.include_router(api_v1_router, prefix="/api/v1")


def _validate_auth_configuration(settings: Settings) -> None:
    """Validate authentication configuration at startup.

    Raises RuntimeError immediately if any auth setting violates the minimum
    security requirements defined in spec.md §13.2 and plan.md §14.
    Failing fast on startup prevents silent misconfiguration reaching production.
    """
    if not settings.JWT_SECRET_KEY:
        raise RuntimeError(
            "JWT_SECRET_KEY is not set. "
            'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(64))"'
        )

    if len(settings.JWT_SECRET_KEY) < 32:
        raise RuntimeError(
            f"JWT_SECRET_KEY is too short ({len(settings.JWT_SECRET_KEY)} chars). "
            "Must be at least 32 characters. "
            'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(64))"'
        )

    logger.info(
        "Authentication configuration validated",
        extra={
            "jwt_algorithm": settings.JWT_ALGORITHM,
            "access_token_expire_minutes": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
            "refresh_token_expire_days": settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS,
            "argon2_memory_cost_kib": settings.ARGON2_MEMORY_COST,
            "lockout_threshold": settings.AUTH_LOCKOUT_THRESHOLD,
        },
    )


app = create_app()
