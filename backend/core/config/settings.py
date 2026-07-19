"""Centralised application settings loaded from environment variables / .env file."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Required fields have no default value and will raise a ValidationError
    if not present in the environment.  Optional fields carry documented
    defaults that are safe for development use.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Platform — Required
    # -------------------------------------------------------------------------

    DATABASE_URL: str = Field(
        ...,
        description="PostgreSQL connection string, e.g. postgresql://user:pass@host/db",
    )
    SECRET_KEY: str = Field(
        ...,
        description="Cryptographic secret for token signing. Min 32 chars.",
    )

    # -------------------------------------------------------------------------
    # Platform — Optional with safe defaults
    # -------------------------------------------------------------------------

    ENVIRONMENT: str = Field(
        "development",
        description="Runtime environment: development | staging | production",
    )
    DEBUG: bool = Field(
        False, description="Enable debug mode (Swagger UI, verbose errors)"
    )
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:3000"],
        description='Allowed CORS origins as a JSON array, e.g. ["https://app.example.com"]',
    )
    LOG_LEVEL: str = Field(
        "INFO", description="Logging level: DEBUG | INFO | WARNING | ERROR | CRITICAL"
    )
    API_VERSION: str = Field(
        "1.0.0", description="API version string surfaced in the health endpoint"
    )
    DB_POOL_SIZE: int = Field(5, description="SQLAlchemy connection pool size")
    DB_MAX_OVERFLOW: int = Field(
        10, description="SQLAlchemy max overflow connections above pool_size"
    )

    # -------------------------------------------------------------------------
    # Authentication — JWT (Epic 002)
    # -------------------------------------------------------------------------

    JWT_SECRET_KEY: str = Field(
        ...,
        description=(
            "Secret key for signing JWT access tokens. "
            'Generate with: python -c "import secrets; print(secrets.token_urlsafe(64))". '
            "Must be at least 32 characters. NEVER hardcode or commit this value."
        ),
    )
    JWT_ALGORITHM: str = Field(
        "HS256",
        description="JWT signing algorithm. HS256 for single-server; RS256 for multi-service.",
    )
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        15,
        description="Access token lifetime in minutes. Default 15 minutes.",
        ge=1,
        le=1440,
    )
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        7,
        description="Standard refresh token lifetime in days (no Remember Me). Default 7 days.",
        ge=1,
        le=365,
    )
    JWT_REMEMBER_ME_EXPIRE_DAYS: int = Field(
        30,
        description="Extended refresh token lifetime in days when Remember Me is selected. Default 30 days.",
        ge=1,
        le=365,
    )
    JWT_ISSUER: str = Field(
        "devsphere-erp",
        description="JWT 'iss' claim value. Must match across all services validating tokens.",
    )
    JWT_AUDIENCE: str = Field(
        "devsphere-erp-api",
        description="JWT 'aud' claim value. Must match the intended token recipient.",
    )
    JWT_CLOCK_SKEW_SECONDS: int = Field(
        30,
        description="Tolerated clock skew in seconds during JWT validation. Default 30 seconds.",
        ge=0,
        le=300,
    )

    # -------------------------------------------------------------------------
    # Authentication — Argon2id (Epic 002)
    # -------------------------------------------------------------------------

    ARGON2_TIME_COST: int = Field(
        3,
        description="Argon2 time cost (number of iterations). Higher = slower = more secure.",
        ge=1,
        le=100,
    )
    ARGON2_MEMORY_COST: int = Field(
        65536,
        description="Argon2 memory cost in kibibytes (64 MiB default). OWASP minimum: 19456.",
        ge=19456,
    )
    ARGON2_PARALLELISM: int = Field(
        4,
        description="Argon2 parallelism (number of threads). Typically set to number of CPU cores.",
        ge=1,
        le=64,
    )

    # -------------------------------------------------------------------------
    # Authentication — Account Lockout (Epic 002)
    # -------------------------------------------------------------------------

    AUTH_LOCKOUT_THRESHOLD: int = Field(
        5,
        description="Number of consecutive failed login attempts before account is locked.",
        ge=1,
        le=100,
    )
    AUTH_LOCKOUT_WINDOW_MINUTES: int = Field(
        15,
        description="Sliding window in minutes over which failed attempts are counted.",
        ge=1,
        le=1440,
    )
    AUTH_LOCKOUT_DURATION_MINUTES: int = Field(
        30,
        description="Duration in minutes that a locked account remains locked before auto-unlock.",
        ge=1,
        le=10080,
    )

    # -------------------------------------------------------------------------
    # Authentication — Password Policy (Epic 002)
    # -------------------------------------------------------------------------

    PASSWORD_MIN_LENGTH: int = Field(
        12,
        description="Minimum password length in characters. NIST SP 800-63B recommends >= 8; OWASP recommends >= 12.",
        ge=8,
        le=128,
    )
    PASSWORD_MAX_LENGTH: int = Field(
        128,
        description="Maximum password length in characters. Prevents DoS via extremely long inputs.",
        ge=64,
        le=1024,
    )
    PASSWORD_HISTORY_COUNT: int = Field(
        5,
        description="Number of previous password hashes retained to prevent reuse.",
        ge=1,
        le=24,
    )

    # -------------------------------------------------------------------------
    # Authentication — Audit Log (Epic 002)
    # -------------------------------------------------------------------------

    AUDIT_LOG_RETENTION_DAYS: int = Field(
        90,
        description="Minimum retention period for audit log records in days. Default 90 days.",
        ge=30,
        le=3650,
    )

    # -------------------------------------------------------------------------
    # Storage — Object Storage / S3-compatible (Epic 003)
    # -------------------------------------------------------------------------

    STORAGE_BACKEND: str = Field(
        "s3",
        description="Storage backend to use: s3 | local",
    )
    S3_ENDPOINT: str | None = Field(
        None,
        description="S3/MinIO endpoint URL. None uses the default AWS endpoint.",
    )
    S3_BUCKET: str = Field(
        "devsphere-companies",
        description="S3 bucket name for company assets (logos, documents).",
    )
    S3_ACCESS_KEY: str = Field(
        "minioadmin",
        description="S3/MinIO access key ID. Override in production. NEVER hardcode production secrets.",
    )
    S3_SECRET_KEY: str = Field(
        "minioadmin",
        description="S3/MinIO secret access key. Override in production. NEVER hardcode production secrets.",
    )
    S3_REGION: str = Field(
        "us-east-1",
        description="AWS/MinIO region. Use us-east-1 for local MinIO.",
    )

    # -------------------------------------------------------------------------
    # Companies — Business Rules (Epic 003)
    # -------------------------------------------------------------------------

    COMPANY_LIMIT: int = Field(
        10,
        description="Maximum companies a single owner can create. 0 = unlimited.",
        ge=0,
    )
    COMPANY_LOGO_MAX_BYTES: int = Field(
        2_097_152,
        description="Maximum allowed company logo file size in bytes. Default 2 MiB.",
        ge=1,
    )
    COMPANY_DELETION_RETENTION_DAYS: int = Field(
        30,
        description="Days soft-deleted companies are retained before permanent deletion.",
        ge=1,
        le=365,
    )
    LOGO_RETENTION_DAYS: int = Field(
        7,
        description="Days a replaced logo is retained in storage before purging.",
        ge=1,
        le=365,
    )

    # -------------------------------------------------------------------------
    # Users & Roles — Business Rules (Epic 004)
    # -------------------------------------------------------------------------

    COMPANY_MAX_MEMBERS: int = Field(
        10_000,
        description="Maximum members allowed per company. 0 = unlimited.",
        ge=0,
    )
    USER_AVATAR_MAX_BYTES: int = Field(
        5_242_880,
        description="Maximum allowed user avatar file size in bytes. Default 5 MiB.",
        ge=1,
    )
    AVATAR_RETENTION_DAYS: int = Field(
        30,
        description="Days a replaced avatar is retained in storage before purging.",
        ge=1,
        le=365,
    )
    MEMBER_DELETION_RETENTION_DAYS: int = Field(
        90,
        description="Days archived members are retained before permanent purge.",
        ge=1,
        le=365,
    )
    MAX_CUSTOM_ROLES_PER_COMPANY: int = Field(
        50,
        description="Maximum custom roles allowed per company.",
        ge=1,
        le=500,
    )
    INVITATION_EXPIRY_DAYS: int = Field(
        7,
        description="Days before a membership invitation expires.",
        ge=1,
        le=90,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton.

    Using lru_cache ensures the .env file is read only once at startup.
    Call get_settings.cache_clear() in tests to force re-reads.
    """
    return Settings()
