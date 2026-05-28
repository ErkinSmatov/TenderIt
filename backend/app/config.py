from pydantic_settings import BaseSettings, SettingsConfigDict


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
    debug: bool = True
    secret_key: str = "change-me-in-production"


settings = Settings()
