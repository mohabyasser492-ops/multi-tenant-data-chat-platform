import uuid
from typing import Any

from pydantic import BaseModel, Field


class SecureQueryRequest(BaseModel):
    sql: str = Field(
        min_length=1,
        max_length=50_000,
        examples=["SELECT email FROM public.users"],
    )


class SecureQueryResponse(BaseModel):
    connection_id: uuid.UUID
    secured_sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    result_size_bytes: int
    execution_time_ms: int
    truncated: bool
    referenced_tables: list[str]
    referenced_columns: list[str]
    applied_limit: int
    row_filters_applied: bool
