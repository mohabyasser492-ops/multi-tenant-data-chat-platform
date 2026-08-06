import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SchemaSyncResponse(BaseModel):
    connection_id: uuid.UUID
    status: str
    schema_count: int
    table_count: int
    column_count: int
    synchronized_at: datetime


class DatabaseColumnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    column_name: str
    data_type: str
    ordinal_position: int | None
    is_nullable: bool | None
    is_primary_key: bool
    is_foreign_key: bool
    is_sensitive: bool
    referenced_schema: str | None
    referenced_table: str | None
    referenced_column: str | None
    description: str | None
    sample_values: list[Any]


class DatabaseTableResponse(BaseModel):
    id: uuid.UUID
    schema_id: uuid.UUID
    schema_name: str
    table_name: str
    table_type: str
    description: str | None
    estimated_row_count: int | None
    primary_key_columns: list[str]
    is_enabled: bool
    is_sensitive: bool
    columns: list[DatabaseColumnResponse]


class DatabaseSchemaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    connection_id: uuid.UUID
    schema_name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class DatabaseSchemaListResponse(BaseModel):
    items: list[DatabaseSchemaResponse]
    total: int


class DatabaseTableListResponse(BaseModel):
    items: list[DatabaseTableResponse]
    total: int
