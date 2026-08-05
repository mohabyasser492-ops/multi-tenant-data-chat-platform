import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    model_validator,
)


class DatabaseType(StrEnum):
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLSERVER = "sqlserver"
    ORACLE = "oracle"


class DatabaseConnectionStatus(StrEnum):
    PENDING = "pending"
    CONNECTED = "connected"
    FAILED = "failed"
    DISABLED = "disabled"


class SchemaSyncStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DatabaseConnectionBase(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=200,
        examples=["Sales PostgreSQL"],
    )
    database_type: DatabaseType
    host: str | None = Field(
        default=None,
        max_length=255,
        examples=["host.docker.internal"],
    )
    port: int | None = Field(
        default=None,
        ge=1,
        le=65535,
        examples=[5432],
    )
    database_name: str | None = Field(
        default=None,
        max_length=255,
        examples=["sales_database"],
    )
    username: str | None = Field(
        default=None,
        max_length=255,
        examples=["readonly_user"],
    )
    ssl_enabled: bool = False
    ssl_settings: dict[str, Any] = Field(default_factory=dict)
    connection_options: dict[str, Any] = Field(default_factory=dict)


class DatabaseConnectionCreate(DatabaseConnectionBase):
    password: SecretStr | None = Field(
        default=None,
        min_length=1,
    )
    connection_string: SecretStr | None = Field(
        default=None,
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_credentials(self) -> "DatabaseConnectionCreate":
        has_connection_string = self.connection_string is not None

        has_individual_fields = all(
            [
                self.host,
                self.port,
                self.database_name,
                self.username,
                self.password,
            ]
        )

        if not has_connection_string and not has_individual_fields:
            raise ValueError(
                "Provide either a connection string or all individual "
                "connection fields."
            )

        return self


class DatabaseConnectionUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=200,
    )
    host: str | None = Field(
        default=None,
        max_length=255,
    )
    port: int | None = Field(
        default=None,
        ge=1,
        le=65535,
    )
    database_name: str | None = Field(
        default=None,
        max_length=255,
    )
    username: str | None = Field(
        default=None,
        max_length=255,
    )
    password: SecretStr | None = Field(
        default=None,
        min_length=1,
    )
    connection_string: SecretStr | None = Field(
        default=None,
        min_length=1,
    )
    ssl_enabled: bool | None = None
    ssl_settings: dict[str, Any] | None = None
    connection_options: dict[str, Any] | None = None
    is_active: bool | None = None


class DatabaseConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    created_by: uuid.UUID | None

    name: str
    database_type: str
    host: str | None
    port: int | None
    database_name: str | None
    username: str | None

    ssl_enabled: bool
    ssl_settings: dict[str, Any]
    connection_options: dict[str, Any]

    status: str
    last_tested_at: datetime | None
    last_test_message: str | None

    schema_sync_status: str
    last_schema_sync_at: datetime | None

    is_active: bool
    created_at: datetime
    updated_at: datetime


class DatabaseConnectionListResponse(BaseModel):
    items: list[DatabaseConnectionResponse]
    total: int


class DatabaseConnectionTestResponse(BaseModel):
    connection_id: uuid.UUID
    success: bool
    status: str
    message: str
    tested_at: datetime
