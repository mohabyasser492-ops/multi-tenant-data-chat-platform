import asyncio
import base64
import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import asyncpg

from core.permissions import AllowedSchema
from models.database_connection import DatabaseConnection
from services.database.connection_tester import (
    build_postgresql_parameters,
)


@dataclass(slots=True)
class QueryExecutionResult:
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    result_size_bytes: int
    execution_time_ms: int
    truncated: bool


class QueryExecutionError(RuntimeError):
    """Raised when secured SQL cannot be executed safely."""


class QueryExecutionTimeoutError(QueryExecutionError):
    """Raised when secured SQL exceeds its execution timeout."""


class QueryResultTooLargeError(QueryExecutionError):
    """Raised when a query result exceeds the configured size limit."""


def serialize_database_value(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, uuid.UUID):
        return str(value)

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")

    if isinstance(value, tuple):
        return [serialize_database_value(item) for item in value]

    if isinstance(value, list):
        return [serialize_database_value(item) for item in value]

    if isinstance(value, dict):
        return {str(key): serialize_database_value(item) for key, item in value.items()}

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):
        return value

    return str(value)


def mask_full(value: Any) -> str | None:
    if value is None:
        return None

    return "********"


def mask_partial(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value)

    if len(text) <= 4:
        return "*" * len(text)

    return text[:2] + ("*" * (len(text) - 4)) + text[-2:]


def mask_email(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value)

    if "@" not in text:
        return mask_partial(text)

    local_part, domain = text.split("@", 1)

    if not local_part:
        masked_local_part = "***"
    elif len(local_part) == 1:
        masked_local_part = f"{local_part}***"
    else:
        masked_local_part = local_part[0] + ("*" * max(len(local_part) - 1, 3))

    return f"{masked_local_part}@{domain}"


def mask_hash(value: Any) -> str | None:
    if value is None:
        return None

    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def apply_mask(
    value: Any,
    mask_type: str | None,
) -> Any:
    if mask_type is None:
        return value

    masks = {
        "full": mask_full,
        "partial": mask_partial,
        "email": mask_email,
        "hash": mask_hash,
    }

    mask_function = masks.get(mask_type)

    if mask_function is None:
        raise QueryExecutionError("The configured column mask is not supported.")

    return mask_function(value)


def get_column_masks(
    allowed_schema: AllowedSchema,
) -> dict[str, str]:
    masks: dict[str, str] = {}

    for table in allowed_schema.tables.values():
        for column in table.columns.values():
            if column.mask_type is not None:
                masks[column.name.lower()] = column.mask_type

    return masks


def serialize_record(
    *,
    record: asyncpg.Record,
    column_masks: dict[str, str],
) -> dict[str, Any]:
    serialized_row: dict[str, Any] = {}

    for column_name, value in record.items():
        serialized_value = serialize_database_value(value)

        mask_type = column_masks.get(column_name.lower())

        serialized_row[column_name] = apply_mask(
            serialized_value,
            mask_type,
        )

    return serialized_row


def calculate_result_size(
    *,
    columns: list[str],
    rows: list[dict[str, Any]],
) -> int:
    serialized_result = json.dumps(
        {
            "columns": columns,
            "rows": rows,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return len(serialized_result.encode("utf-8"))


async def execute_postgresql_query(
    *,
    connection: DatabaseConnection,
    sql: str,
    allowed_schema: AllowedSchema,
    timeout_seconds: int,
    maximum_result_bytes: int,
) -> QueryExecutionResult:
    if timeout_seconds < 1:
        raise QueryExecutionError("The execution timeout must be positive.")

    if maximum_result_bytes < 1:
        raise QueryExecutionError("The result-size limit must be positive.")

    parameters = build_postgresql_parameters(connection)

    source_connection: asyncpg.Connection | None = None
    started_at = asyncio.get_running_loop().time()

    try:
        source_connection = await asyncio.wait_for(
            asyncpg.connect(
                **parameters,
                ssl=("require" if connection.ssl_enabled else None),
                command_timeout=timeout_seconds,
                server_settings={
                    "application_name": ("multi_tenant_data_chat_query"),
                    "default_transaction_read_only": "on",
                },
            ),
            timeout=timeout_seconds,
        )

        transaction = source_connection.transaction(
            readonly=True,
        )

        async with transaction:
            await source_connection.execute(
                "SELECT set_config('statement_timeout', $1, true)",
                f"{timeout_seconds * 1000}ms",
            )

            records = await asyncio.wait_for(
                source_connection.fetch(sql),
                timeout=timeout_seconds,
            )

        columns = list(records[0].keys()) if records else []

        column_masks = get_column_masks(allowed_schema)

        rows: list[dict[str, Any]] = []

        for record in records:
            serialized_row = serialize_record(
                record=record,
                column_masks=column_masks,
            )

            rows.append(serialized_row)

            current_size = calculate_result_size(
                columns=columns,
                rows=rows,
            )

            if current_size > maximum_result_bytes:
                raise QueryResultTooLargeError(
                    "The query result exceeded the configured size limit."
                )

        result_size_bytes = calculate_result_size(
            columns=columns,
            rows=rows,
        )

        finished_at = asyncio.get_running_loop().time()

        execution_time_ms = int((finished_at - started_at) * 1000)

        return QueryExecutionResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            result_size_bytes=result_size_bytes,
            execution_time_ms=execution_time_ms,
            truncated=False,
        )

    except TimeoutError as exc:
        raise QueryExecutionTimeoutError("The query execution timed out.") from exc
    except QueryResultTooLargeError:
        raise
    except (
        asyncpg.PostgresError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        raise QueryExecutionError("The secured query could not be executed.") from exc
    finally:
        if source_connection is not None:
            await source_connection.close()


async def execute_secured_query(
    *,
    connection: DatabaseConnection,
    sql: str,
    allowed_schema: AllowedSchema,
    timeout_seconds: int,
    maximum_result_bytes: int,
) -> QueryExecutionResult:
    if connection.database_type != "postgresql":
        raise QueryExecutionError(
            "Query execution is currently available for PostgreSQL connections."
        )

    return await execute_postgresql_query(
        connection=connection,
        sql=sql,
        allowed_schema=allowed_schema,
        timeout_seconds=timeout_seconds,
        maximum_result_bytes=maximum_result_bytes,
    )
