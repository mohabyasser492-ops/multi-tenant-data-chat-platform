import uuid
from copy import deepcopy

from sqlalchemy.ext.asyncio import AsyncSession

from core.permissions import (
    AllowedColumn,
    AllowedSchema,
    AllowedTable,
)
from models.user import User
from repositories.effective_permissions import (
    get_effective_column_permissions,
    get_effective_table_permissions,
    get_user_role_ids,
)
from services.database.connection_service import (
    get_database_connection,
)


def merge_row_filter(
    existing_filters: list[dict],
    row_filter: dict,
) -> None:
    rules = row_filter.get("rules", [])

    if rules:
        existing_filters.append(deepcopy(row_filter))


async def build_permission_filtered_schema(
    *,
    session: AsyncSession,
    current_user: User,
    connection_id: uuid.UUID,
) -> AllowedSchema:
    await get_database_connection(
        session=session,
        current_user=current_user,
        connection_id=connection_id,
    )

    role_ids = await get_user_role_ids(
        session=session,
        user_id=current_user.id,
    )

    permission_rows = await get_effective_table_permissions(
        session=session,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        connection_id=connection_id,
        role_ids=role_ids,
    )

    readable_permission_rows = [row for row in permission_rows if row[0].can_read]

    permission_ids = [permission.id for permission, _, _ in readable_permission_rows]

    column_rows = await get_effective_column_permissions(
        session=session,
        tenant_id=current_user.tenant_id,
        table_permission_ids=permission_ids,
    )

    columns_by_permission: dict[
        uuid.UUID,
        list[tuple],
    ] = {}

    for column_permission, column in column_rows:
        columns_by_permission.setdefault(
            column_permission.table_permission_id,
            [],
        ).append(
            (
                column_permission,
                column,
            )
        )

    allowed_schema = AllowedSchema(connection_id=str(connection_id))

    for permission, table, schema in readable_permission_rows:
        qualified_name = f"{schema.schema_name}.{table.table_name}"

        allowed_table = allowed_schema.tables.get(qualified_name)

        if allowed_table is None:
            allowed_table = AllowedTable(
                table_id=str(table.id),
                schema_name=schema.schema_name,
                table_name=table.table_name,
                can_read=permission.can_read,
                can_insert=permission.can_insert,
                can_update=permission.can_update,
                can_delete=permission.can_delete,
            )

            allowed_schema.tables[qualified_name] = allowed_table
        else:
            allowed_table.can_read = allowed_table.can_read or permission.can_read
            allowed_table.can_insert = allowed_table.can_insert or permission.can_insert
            allowed_table.can_update = allowed_table.can_update or permission.can_update
            allowed_table.can_delete = allowed_table.can_delete or permission.can_delete

        merge_row_filter(
            allowed_table.row_filters,
            permission.row_filter,
        )

        for (
            column_permission,
            column,
        ) in columns_by_permission.get(
            permission.id,
            [],
        ):
            if not column_permission.can_read:
                continue

            existing_column = allowed_table.columns.get(column.column_name)

            if existing_column is None:
                allowed_table.columns[column.column_name] = AllowedColumn(
                    column_id=str(column.id),
                    name=column.column_name,
                    data_type=column.data_type,
                    can_read=True,
                    can_filter=(column_permission.can_filter),
                    can_aggregate=(column_permission.can_aggregate),
                    mask_type=column_permission.mask_type,
                )
            else:
                existing_column.can_filter = (
                    existing_column.can_filter or column_permission.can_filter
                )
                existing_column.can_aggregate = (
                    existing_column.can_aggregate or column_permission.can_aggregate
                )

                if (
                    existing_column.mask_type is None
                    and column_permission.mask_type is not None
                ):
                    existing_column.mask_type = column_permission.mask_type

    empty_tables = [
        qualified_name
        for qualified_name, table in allowed_schema.tables.items()
        if not table.columns
    ]

    for qualified_name in empty_tables:
        del allowed_schema.tables[qualified_name]

    return allowed_schema
