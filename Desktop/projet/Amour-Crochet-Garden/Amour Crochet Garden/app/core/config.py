"""Application configuration."""

import os
from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_WEAK_SECRET_KEYS = frozenset(
    {
        "dev-secret-change-in-production",
        "change-me-in-production-use-long-random-string",
        "change-me",
        "secret",
        "changeme",
    }
)


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    secret_key: str = "dev-secret-change-in-production"
    database_url: str = "sqlite+aiosqlite:///./amour_crochet.db"
    admin_username: str = "admin"
    admin_password: str = "admin123"
    contact_email: str = "contact@amourcrochetgarden.fr"
    max_upload_size_mb: int = 5
    debug: bool = False
    # En DEBUG, paiement et e-mails sont mockés par défaut (voir mock_payments / mock_emails)
    mock_payments: bool | None = None
    mock_emails: bool | None = None
    sumup_api_key: str = ""
    sumup_merchant_code: str = ""
    # Email (SMTP) — confirmation client + alerte admin
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    order_notify_email: str = ""
    # NIS2: HTTPS-only session cookies in production
    https_only: bool = False
    # Comma-separated hostnames allowed in production (empty = skip TrustedHost)
    allowed_hosts: str = ""

    @property
    def is_production(self) -> bool:
        return os.getenv("PRODUCTION") == "1" or (not self.debug and self.https_only)

    @property
    def payments_mocked(self) -> bool:
        # Never allow mock payments in production
        if self.is_production or os.getenv("PRODUCTION") == "1":
            return False
        if self.mock_payments is not None:
            return self.mock_payments
        return self.debug

    @property
    def emails_mocked(self) -> bool:
        if os.getenv("PRODUCTION") == "1":
            return False
        if self.mock_emails is not None:
            return self.mock_emails
        return self.debug

    @property
    def allowed_hosts_list(self) -> list[str]:
        raw = (self.allowed_hosts or "").strip()
        if not raw:
            return []
        return [h.strip() for h in raw.split(",") if h.strip()]

    @field_validator("smtp_password")
    @classmethod
    def normalize_smtp_password(cls, v: str) -> str:
        """Gmail app passwords are often pasted with spaces — strip them."""
        return v.replace(" ", "") if v else v

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Reject weak/default secrets always (not only in production)."""
        if not v or v in _WEAK_SECRET_KEYS or len(v) < 32:
            raise ValueError(
                "SECRET_KEY must be a strong random string (>= 32 chars). "
                'Generate: python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return v

    @model_validator(mode="after")
    def validate_production_guards(self):
        if os.getenv("PRODUCTION") == "1":
            if self.debug:
                raise ValueError("DEBUG must be false when PRODUCTION=1")
            if self.mock_payments is True:
                raise ValueError("MOCK_PAYMENTS must be false when PRODUCTION=1")
            if not self.https_only:
                raise ValueError("HTTPS_ONLY must be true when PRODUCTION=1")
            weak_passwords = {"admin123", "password", "admin", "123456", "changeme"}
            if self.admin_password in weak_passwords or len(self.admin_password) < 12:
                raise ValueError(
                    "ADMIN_PASSWORD must be strong (>= 12 chars) when PRODUCTION=1"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
