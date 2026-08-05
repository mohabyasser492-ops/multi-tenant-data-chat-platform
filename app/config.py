from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Multi-Tenant Data Chat Platform"
    app_env: Literal["development", "testing", "production"] = "development"
    debug: bool = False
    api_prefix: str = "/api"

    # Platform database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "data_chat"
    postgres_user: str = "data_chat"
    postgres_password: str
    database_url: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str = "documents"
    minio_secure: bool = False

    # Authentication
    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, gt=0)
    refresh_token_expire_days: int = Field(default=7, gt=0)

    # Encryption
    fernet_key: str

    # Embeddings
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = Field(default=384, gt=0)

    # LLM
    llm_provider: str = "mock"
    llm_api_key: str = ""
    llm_model: str = ""

    # SQL safety
    sql_default_row_limit: int = Field(default=100, gt=0, le=10_000)
    sql_max_result_bytes: int = Field(default=1_048_576, gt=0)
    sql_timeout_seconds: int = Field(default=10, gt=0, le=300)

    # Uploads
    max_upload_size_mb: int = Field(default=25, gt=0, le=500)
    allowed_extensions: list[str] = Field(
        default_factory=lambda: [
            "pdf",
            "docx",
            "xlsx",
            "xls",
            "csv",
            "txt",
        ]
    )

    @field_validator("api_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        if not value.startswith("/"):
            return f"/{value}"
        return value

    # Initial tenant administrator
    initial_tenant_name: str = "Demo Company"
    initial_tenant_code: str = "demo"
    initial_admin_email: str = "admin@example.com"
    initial_admin_full_name: str = "Platform Administrator"
    initial_admin_password: str = Field(
        default="replace_with_a_strong_password",
        min_length=8,
        max_length=128,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
