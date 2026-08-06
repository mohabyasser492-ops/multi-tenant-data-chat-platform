import asyncio
from dataclasses import dataclass, field
from typing import Any

import asyncpg

from models.database_connection import DatabaseConnection
from services.database.connection_tester import (
    build_postgresql_parameters,
)


@dataclass(slots=True)
class DiscoveredColumn:
    column_name: str
    data_type: str
    ordinal_position: int
    is_nullable: bool
    is_primary_key: bool = False
    is_foreign_key: bool = False
    referenced_schema: str | None = None
    referenced_table: str | None = None
    referenced_column: str | None = None


@dataclass(slots=True)
class DiscoveredTable:
    schema_name: str
    table_name: str
    table_type: str
    estimated_row_count: int | None
    primary_key_columns: list[str] = field(default_factory=list)
    columns: list[DiscoveredColumn] = field(default_factory=list)


@dataclass(slots=True)
class DiscoveredSchema:
    schema_name: str
    tables: list[DiscoveredTable] = field(default_factory=list)


@dataclass(slots=True)
class SchemaDiscoveryResult:
    schemas: list[DiscoveredSchema]
    schema_count: int
    table_count: int
    column_count: int


class SchemaDiscoveryError(RuntimeError):
    """Raised when source-database metadata cannot be discovered."""


SCHEMA_QUERY = """
SELECT schema_name
FROM information_schema.schemata
WHERE schema_name NOT IN (
    'pg_catalog',
    'information_schema',
    'pg_toast'
)
AND schema_name NOT LIKE 'pg_temp_%'
AND schema_name NOT LIKE 'pg_toast_temp_%'
ORDER BY schema_name
"""


TABLE_QUERY = """
SELECT
    table_schema,
    table_name,
    CASE
        WHEN table_type = 'BASE TABLE' THEN 'table'
        WHEN table_type = 'VIEW' THEN 'view'
        ELSE LOWER(table_type)
    END AS table_type
FROM information_schema.tables
WHERE table_schema NOT IN (
    'pg_catalog',
    'information_schema',
    'pg_toast'
)
AND table_schema NOT LIKE 'pg_temp_%'
AND table_schema NOT LIKE 'pg_toast_temp_%'
ORDER BY table_schema, table_name
"""


COLUMN_QUERY = """
SELECT
    table_schema,
    table_name,
    column_name,
    data_type,
    ordinal_position,
    is_nullable
FROM information_schema.columns
WHERE table_schema NOT IN (
    'pg_catalog',
    'information_schema',
    'pg_toast'
)
AND table_schema NOT LIKE 'pg_temp_%'
AND table_schema NOT LIKE 'pg_toast_temp_%'
ORDER BY table_schema, table_name, ordinal_position
"""


PRIMARY_KEY_QUERY = """
SELECT
    table_schema,
    table_name,
    column_name
FROM information_schema.key_column_usage
WHERE constraint_name IN (
    SELECT constraint_name
    FROM information_schema.table_constraints
    WHERE constraint_type = 'PRIMARY KEY'
)
AND table_schema NOT IN (
    'pg_catalog',
    'information_schema',
    'pg_toast'
)
ORDER BY table_schema, table_name, ordinal_position
"""


FOREIGN_KEY_QUERY = """
SELECT
    tc.table_schema,
    tc.table_name,
    kcu.column_name,
    ccu.table_schema AS referenced_schema,
    ccu.table_name AS referenced_table,
    ccu.column_name AS referenced_column
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.constraint_schema = kcu.constraint_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON tc.constraint_name = ccu.constraint_name
    AND tc.constraint_schema = ccu.constraint_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
AND tc.table_schema NOT IN (
    'pg_catalog',
    'information_schema',
    'pg_toast'
)
ORDER BY
    tc.table_schema,
    tc.table_name,
    kcu.ordinal_position
"""


ROW_COUNT_QUERY = """
SELECT
    schemaname AS table_schema,
    relname AS table_name,
    n_live_tup::BIGINT AS estimated_row_count
FROM pg_stat_user_tables
"""


def _record_key(
    schema_name: str,
    table_name: str,
) -> tuple[str, str]:
    return schema_name, table_name


async def discover_postgresql_schema(
    connection: DatabaseConnection,
    *,
    timeout_seconds: int = 15,
) -> SchemaDiscoveryResult:
    parameters = build_postgresql_parameters(connection)
    source_connection: asyncpg.Connection | None = None

    try:
        source_connection = await asyncio.wait_for(
            asyncpg.connect(
                **parameters,
                ssl="require" if connection.ssl_enabled else None,
                command_timeout=timeout_seconds,
                server_settings={
                    "application_name": ("multi_tenant_data_chat_schema_discovery"),
                    "default_transaction_read_only": "on",
                },
            ),
            timeout=timeout_seconds,
        )

        schema_rows = await asyncio.wait_for(
            source_connection.fetch(SCHEMA_QUERY),
            timeout=timeout_seconds,
        )
        table_rows = await asyncio.wait_for(
            source_connection.fetch(TABLE_QUERY),
            timeout=timeout_seconds,
        )
        column_rows = await asyncio.wait_for(
            source_connection.fetch(COLUMN_QUERY),
            timeout=timeout_seconds,
        )
        primary_key_rows = await asyncio.wait_for(
            source_connection.fetch(PRIMARY_KEY_QUERY),
            timeout=timeout_seconds,
        )
        foreign_key_rows = await asyncio.wait_for(
            source_connection.fetch(FOREIGN_KEY_QUERY),
            timeout=timeout_seconds,
        )
        row_count_rows = await asyncio.wait_for(
            source_connection.fetch(ROW_COUNT_QUERY),
            timeout=timeout_seconds,
        )

    except TimeoutError as exc:
        raise SchemaDiscoveryError("Schema discovery timed out.") from exc
    except (
        asyncpg.PostgresError,
        OSError,
        ValueError,
    ) as exc:
        raise SchemaDiscoveryError("Schema discovery failed.") from exc
    finally:
        if source_connection is not None:
            await source_connection.close()

    return build_discovery_result(
        schema_rows=schema_rows,
        table_rows=table_rows,
        column_rows=column_rows,
        primary_key_rows=primary_key_rows,
        foreign_key_rows=foreign_key_rows,
        row_count_rows=row_count_rows,
    )


def build_discovery_result(
    *,
    schema_rows: list[Any],
    table_rows: list[Any],
    column_rows: list[Any],
    primary_key_rows: list[Any],
    foreign_key_rows: list[Any],
    row_count_rows: list[Any],
) -> SchemaDiscoveryResult:
    primary_keys: dict[tuple[str, str], list[str]] = {}

    for row in primary_key_rows:
        key = _record_key(
            row["table_schema"],
            row["table_name"],
        )
        primary_keys.setdefault(key, []).append(row["column_name"])

    foreign_keys: dict[
        tuple[str, str, str],
        tuple[str, str, str],
    ] = {}

    for row in foreign_key_rows:
        foreign_keys[
            (
                row["table_schema"],
                row["table_name"],
                row["column_name"],
            )
        ] = (
            row["referenced_schema"],
            row["referenced_table"],
            row["referenced_column"],
        )

    estimated_row_counts = {
        _record_key(
            row["table_schema"],
            row["table_name"],
        ): row["estimated_row_count"]
        for row in row_count_rows
    }

    discovered_columns: dict[
        tuple[str, str],
        list[DiscoveredColumn],
    ] = {}

    for row in column_rows:
        table_key = _record_key(
            row["table_schema"],
            row["table_name"],
        )
        column_key = (
            row["table_schema"],
            row["table_name"],
            row["column_name"],
        )

        foreign_key = foreign_keys.get(column_key)
        referenced_schema = None
        referenced_table = None
        referenced_column = None

        if foreign_key is not None:
            (
                referenced_schema,
                referenced_table,
                referenced_column,
            ) = foreign_key

        discovered_column = DiscoveredColumn(
            column_name=row["column_name"],
            data_type=row["data_type"],
            ordinal_position=row["ordinal_position"],
            is_nullable=row["is_nullable"] == "YES",
            is_primary_key=(row["column_name"] in primary_keys.get(table_key, [])),
            is_foreign_key=foreign_key is not None,
            referenced_schema=referenced_schema,
            referenced_table=referenced_table,
            referenced_column=referenced_column,
        )

        discovered_columns.setdefault(
            table_key,
            [],
        ).append(discovered_column)

    discovered_tables: dict[str, list[DiscoveredTable]] = {}

    for row in table_rows:
        table_key = _record_key(
            row["table_schema"],
            row["table_name"],
        )

        table = DiscoveredTable(
            schema_name=row["table_schema"],
            table_name=row["table_name"],
            table_type=row["table_type"],
            estimated_row_count=estimated_row_counts.get(table_key),
            primary_key_columns=primary_keys.get(
                table_key,
                [],
            ),
            columns=discovered_columns.get(
                table_key,
                [],
            ),
        )

        discovered_tables.setdefault(
            row["table_schema"],
            [],
        ).append(table)

    schemas = [
        DiscoveredSchema(
            schema_name=row["schema_name"],
            tables=discovered_tables.get(
                row["schema_name"],
                [],
            ),
        )
        for row in schema_rows
    ]

    table_count = sum(len(schema.tables) for schema in schemas)
    column_count = sum(
        len(table.columns) for schema in schemas for table in schema.tables
    )

    return SchemaDiscoveryResult(
        schemas=schemas,
        schema_count=len(schemas),
        table_count=table_count,
        column_count=column_count,
    )


async def discover_database_schema(
    connection: DatabaseConnection,
    *,
    timeout_seconds: int = 15,
) -> SchemaDiscoveryResult:
    if connection.database_type != "postgresql":
        raise SchemaDiscoveryError(
            "Schema discovery is currently available for PostgreSQL."
        )

    return await discover_postgresql_schema(
        connection,
        timeout_seconds=timeout_seconds,
    )
