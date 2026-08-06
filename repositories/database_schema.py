import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database_schema import (
    DatabaseColumn,
    DatabaseSchema,
    DatabaseTable,
)


async def list_cached_schemas(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID,
) -> tuple[list[DatabaseSchema], int]:
    items_result = await session.execute(
        select(DatabaseSchema)
        .where(
            DatabaseSchema.tenant_id == tenant_id,
            DatabaseSchema.connection_id == connection_id,
        )
        .order_by(DatabaseSchema.schema_name)
    )

    total_result = await session.execute(
        select(func.count(DatabaseSchema.id)).where(
            DatabaseSchema.tenant_id == tenant_id,
            DatabaseSchema.connection_id == connection_id,
        )
    )

    return (
        list(items_result.scalars().all()),
        total_result.scalar_one(),
    )


async def list_cached_tables(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID,
    schema_name: str | None = None,
) -> tuple[
    list[tuple[DatabaseTable, str]],
    dict[uuid.UUID, list[DatabaseColumn]],
    int,
]:
    table_query = (
        select(
            DatabaseTable,
            DatabaseSchema.schema_name,
        )
        .join(
            DatabaseSchema,
            DatabaseTable.schema_id == DatabaseSchema.id,
        )
        .where(
            DatabaseTable.tenant_id == tenant_id,
            DatabaseTable.connection_id == connection_id,
            DatabaseSchema.tenant_id == tenant_id,
            DatabaseSchema.connection_id == connection_id,
        )
    )

    count_query = (
        select(func.count(DatabaseTable.id))
        .join(
            DatabaseSchema,
            DatabaseTable.schema_id == DatabaseSchema.id,
        )
        .where(
            DatabaseTable.tenant_id == tenant_id,
            DatabaseTable.connection_id == connection_id,
            DatabaseSchema.tenant_id == tenant_id,
            DatabaseSchema.connection_id == connection_id,
        )
    )

    if schema_name is not None:
        table_query = table_query.where(DatabaseSchema.schema_name == schema_name)
        count_query = count_query.where(DatabaseSchema.schema_name == schema_name)

    table_query = table_query.order_by(
        DatabaseSchema.schema_name,
        DatabaseTable.table_name,
    )

    table_result = await session.execute(table_query)
    table_rows = list(table_result.all())

    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    table_ids = [table.id for table, _ in table_rows]

    columns_by_table: dict[
        uuid.UUID,
        list[DatabaseColumn],
    ] = {}

    if table_ids:
        column_result = await session.execute(
            select(DatabaseColumn)
            .where(
                DatabaseColumn.tenant_id == tenant_id,
                DatabaseColumn.table_id.in_(table_ids),
            )
            .order_by(
                DatabaseColumn.table_id,
                DatabaseColumn.ordinal_position,
            )
        )

        for column in column_result.scalars().all():
            columns_by_table.setdefault(
                column.table_id,
                [],
            ).append(column)

    return table_rows, columns_by_table, total
