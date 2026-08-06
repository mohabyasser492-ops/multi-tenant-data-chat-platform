import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from models.database_schema import DatabaseSchema
from models.user import User
from repositories.database_schema import (
    list_cached_schemas,
    list_cached_tables,
)
from schemas.database_schema import (
    DatabaseColumnResponse,
    DatabaseTableResponse,
)
from services.database.connection_service import (
    get_database_connection,
)


async def get_cached_schemas(
    *,
    session: AsyncSession,
    current_user: User,
    connection_id: uuid.UUID,
) -> tuple[list[DatabaseSchema], int]:
    await get_database_connection(
        session=session,
        current_user=current_user,
        connection_id=connection_id,
    )

    return await list_cached_schemas(
        session=session,
        tenant_id=current_user.tenant_id,
        connection_id=connection_id,
    )


async def get_cached_tables(
    *,
    session: AsyncSession,
    current_user: User,
    connection_id: uuid.UUID,
    schema_name: str | None,
) -> tuple[list[DatabaseTableResponse], int]:
    await get_database_connection(
        session=session,
        current_user=current_user,
        connection_id=connection_id,
    )

    table_rows, columns_by_table, total = await list_cached_tables(
        session=session,
        tenant_id=current_user.tenant_id,
        connection_id=connection_id,
        schema_name=schema_name,
    )

    items: list[DatabaseTableResponse] = []

    for table, cached_schema_name in table_rows:
        columns = [
            DatabaseColumnResponse.model_validate(column)
            for column in columns_by_table.get(table.id, [])
        ]

        items.append(
            DatabaseTableResponse(
                id=table.id,
                schema_id=table.schema_id,
                schema_name=cached_schema_name,
                table_name=table.table_name,
                table_type=table.table_type,
                description=table.description,
                estimated_row_count=table.estimated_row_count,
                primary_key_columns=table.primary_key_columns,
                is_enabled=table.is_enabled,
                is_sensitive=table.is_sensitive,
                columns=columns,
            )
        )

    return items, total
