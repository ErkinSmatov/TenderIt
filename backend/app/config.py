from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET = "change-me-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    database_url: str = (
        "postgresql+asyncpg://tenderit:tenderit_dev@localhost:5432/tenderit"
    )
    redis_url: str = "redis://localhost:6379"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin_dev"
    minio_secure: bool = False
    debug: bool = True
    secret_key: str = _DEFAULT_SECRET
    # Phase 2: JWT + email + frontend settings
    jwt_secret: str = _DEFAULT_SECRET
    resend_api_key: str = ""
    frontend_url: str = "http://localhost:3000"
    # Phase 3: goszakup Unified Services GraphQL API (token via GOSZAKUP_API_TOKEN env)
    # Empty default so tests run without a real token (respx mocks replace HTTP layer).
    goszakup_api_token: str = ""

    @model_validator(mode="after")
    def validate_secrets(self) -> "Settings":
        """WR-04: Fail at startup if default placeholder secrets are used in production.

        debug=True (development / test) is exempt — allows running without .env.
        debug=False (production) with a default secret is a deployment error.
        """
        if not self.debug and self.jwt_secret == _DEFAULT_SECRET:
            raise ValueError(
                "jwt_secret must be set in production (debug=False). "
                "Set JWT_SECRET env var or add it to .env."
            )
        return self


settings = Settings()
