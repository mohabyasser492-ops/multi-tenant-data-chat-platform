import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database_schema import (
    DatabaseColumn,
    DatabaseSchema,
    DatabaseTable,
)
from services.database.schema_discovery import (
    SchemaDiscoveryResult,
)


async def clear_connection_metadata(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID,
) -> None:
    schema_ids_result = await session.execute(
        select(DatabaseSchema.id).where(
            DatabaseSchema.tenant_id == tenant_id,
            DatabaseSchema.connection_id == connection_id,
        )
    )
    schema_ids = list(schema_ids_result.scalars().all())

    if schema_ids:
        table_ids_result = await session.execute(
            select(DatabaseTable.id).where(
                DatabaseTable.tenant_id == tenant_id,
                DatabaseTable.connection_id == connection_id,
                DatabaseTable.schema_id.in_(schema_ids),
            )
        )
        table_ids = list(table_ids_result.scalars().all())

        if table_ids:
            await session.execute(
                delete(DatabaseColumn).where(
                    DatabaseColumn.tenant_id == tenant_id,
                    DatabaseColumn.table_id.in_(table_ids),
                )
            )

        await session.execute(
            delete(DatabaseTable).where(
                DatabaseTable.tenant_id == tenant_id,
                DatabaseTable.connection_id == connection_id,
            )
        )

        await session.execute(
            delete(DatabaseSchema).where(
                DatabaseSchema.tenant_id == tenant_id,
                DatabaseSchema.connection_id == connection_id,
            )
        )

    await session.flush()


async def cache_discovered_metadata(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID,
    discovery: SchemaDiscoveryResult,
) -> tuple[int, int, int]:
    await clear_connection_metadata(
        session=session,
        tenant_id=tenant_id,
        connection_id=connection_id,
    )

    cached_schema_count = 0
    cached_table_count = 0
    cached_column_count = 0

    for discovered_schema in discovery.schemas:
        schema = DatabaseSchema(
            tenant_id=tenant_id,
            connection_id=connection_id,
            schema_name=discovered_schema.schema_name,
            description=None,
        )

        session.add(schema)
        await session.flush()

        cached_schema_count += 1

        for discovered_table in discovered_schema.tables:
            table = DatabaseTable(
                tenant_id=tenant_id,
                connection_id=connection_id,
                schema_id=schema.id,
                table_name=discovered_table.table_name,
                table_type=discovered_table.table_type,
                description=None,
                estimated_row_count=(discovered_table.estimated_row_count),
                primary_key_columns=(discovered_table.primary_key_columns),
                is_enabled=True,
                is_sensitive=False,
                table_metadata={},
            )

            session.add(table)
            await session.flush()

            cached_table_count += 1

            for discovered_column in discovered_table.columns:
                column = DatabaseColumn(
                    tenant_id=tenant_id,
                    table_id=table.id,
                    column_name=discovered_column.column_name,
                    data_type=discovered_column.data_type,
                    ordinal_position=(discovered_column.ordinal_position),
                    is_nullable=discovered_column.is_nullable,
                    is_primary_key=(discovered_column.is_primary_key),
                    is_foreign_key=(discovered_column.is_foreign_key),
                    is_sensitive=False,
                    referenced_schema=(discovered_column.referenced_schema),
                    referenced_table=(discovered_column.referenced_table),
                    referenced_column=(discovered_column.referenced_column),
                    description=None,
                    sample_values=[],
                )

                session.add(column)
                cached_column_count += 1

    await session.commit()

    return (
        cached_schema_count,
        cached_table_count,
        cached_column_count,
    )
