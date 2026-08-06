import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database_schema import (
    DatabaseColumn,
    DatabaseTable,
)
from models.role import Role
from models.table_permission import (
    ColumnPermission,
    TablePermission,
)
from models.user import User
from repositories.permissions import (
    create_table_permission,
    find_existing_table_permission,
    list_column_permissions,
    list_table_permissions,
)
from schemas.permission import (
    TablePermissionCreate,
    TablePermissionResponse,
)
from services.database.connection_service import (
    get_database_connection,
    require_tenant_administrator,
)


class PermissionResourceNotFoundError(LookupError):
    """Raised when a referenced permission resource is unavailable."""


class DuplicateTablePermissionError(ValueError):
    """Raised when a subject already has a permission for a table."""


async def validate_permission_table(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID,
    table_id: uuid.UUID,
) -> DatabaseTable:
    result = await session.execute(
        select(DatabaseTable).where(
            DatabaseTable.id == table_id,
            DatabaseTable.tenant_id == tenant_id,
            DatabaseTable.connection_id == connection_id,
        )
    )

    table = result.scalar_one_or_none()

    if table is None:
        raise PermissionResourceNotFoundError(
            "The selected database table was not found."
        )

    return table


async def validate_permission_subject(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    role_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
) -> None:
    if role_id is not None:
        result = await session.execute(
            select(Role.id).where(
                Role.id == role_id,
                Role.tenant_id == tenant_id,
            )
        )

        if result.scalar_one_or_none() is None:
            raise PermissionResourceNotFoundError("The selected role was not found.")

    if user_id is not None:
        result = await session.execute(
            select(User.id).where(
                User.id == user_id,
                User.tenant_id == tenant_id,
            )
        )

        if result.scalar_one_or_none() is None:
            raise PermissionResourceNotFoundError("The selected user was not found.")


async def validate_permission_columns(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    table_id: uuid.UUID,
    column_ids: list[uuid.UUID],
) -> None:
    if not column_ids:
        return

    if len(column_ids) != len(set(column_ids)):
        raise ValueError("Column permissions cannot contain duplicate columns.")

    result = await session.execute(
        select(DatabaseColumn.id).where(
            DatabaseColumn.tenant_id == tenant_id,
            DatabaseColumn.table_id == table_id,
            DatabaseColumn.id.in_(column_ids),
        )
    )

    valid_column_ids = set(result.scalars().all())

    if valid_column_ids != set(column_ids):
        raise PermissionResourceNotFoundError(
            "One or more selected columns were not found."
        )


async def create_permission(
    *,
    session: AsyncSession,
    current_user: User,
    request: TablePermissionCreate,
) -> TablePermissionResponse:
    require_tenant_administrator(current_user)

    await get_database_connection(
        session=session,
        current_user=current_user,
        connection_id=request.connection_id,
    )

    await validate_permission_table(
        session=session,
        tenant_id=current_user.tenant_id,
        connection_id=request.connection_id,
        table_id=request.table_id,
    )

    await validate_permission_subject(
        session=session,
        tenant_id=current_user.tenant_id,
        role_id=request.role_id,
        user_id=request.user_id,
    )

    column_ids = [column.column_id for column in request.columns]

    await validate_permission_columns(
        session=session,
        tenant_id=current_user.tenant_id,
        table_id=request.table_id,
        column_ids=column_ids,
    )

    existing = await find_existing_table_permission(
        session=session,
        tenant_id=current_user.tenant_id,
        table_id=request.table_id,
        role_id=request.role_id,
        user_id=request.user_id,
    )

    if existing is not None:
        raise DuplicateTablePermissionError(
            "The permission subject already has access rules for this table."
        )

    permission = TablePermission(
        tenant_id=current_user.tenant_id,
        role_id=request.role_id,
        user_id=request.user_id,
        connection_id=request.connection_id,
        table_id=request.table_id,
        can_read=request.can_read,
        can_insert=request.can_insert,
        can_update=request.can_update,
        can_delete=request.can_delete,
        row_filter=request.row_filter.model_dump(mode="json"),
    )

    column_permissions = [
        ColumnPermission(
            table_permission_id=uuid.uuid4(),
            column_id=column.column_id,
            can_read=column.can_read,
            can_filter=column.can_filter,
            can_aggregate=column.can_aggregate,
            mask_type=(
                column.mask_type.value if column.mask_type is not None else None
            ),
        )
        for column in request.columns
    ]

    saved_permission = await create_table_permission(
        session=session,
        permission=permission,
        column_permissions=column_permissions,
    )

    return TablePermissionResponse(
        id=saved_permission.id,
        tenant_id=saved_permission.tenant_id,
        role_id=saved_permission.role_id,
        user_id=saved_permission.user_id,
        connection_id=saved_permission.connection_id,
        table_id=saved_permission.table_id,
        can_read=saved_permission.can_read,
        can_insert=saved_permission.can_insert,
        can_update=saved_permission.can_update,
        can_delete=saved_permission.can_delete,
        row_filter=saved_permission.row_filter,
        columns=column_permissions,
    )


async def get_permissions(
    *,
    session: AsyncSession,
    current_user: User,
    connection_id: uuid.UUID | None,
    table_id: uuid.UUID | None,
) -> tuple[list[TablePermissionResponse], int]:
    if connection_id is not None:
        await get_database_connection(
            session=session,
            current_user=current_user,
            connection_id=connection_id,
        )

    permissions, total = await list_table_permissions(
        session=session,
        tenant_id=current_user.tenant_id,
        connection_id=connection_id,
        table_id=table_id,
    )

    permission_ids = [permission.id for permission in permissions]

    columns_by_permission = await list_column_permissions(
        session=session,
        table_permission_ids=permission_ids,
    )

    items = [
        TablePermissionResponse(
            id=permission.id,
            tenant_id=permission.tenant_id,
            role_id=permission.role_id,
            user_id=permission.user_id,
            connection_id=permission.connection_id,
            table_id=permission.table_id,
            can_read=permission.can_read,
            can_insert=permission.can_insert,
            can_update=permission.can_update,
            can_delete=permission.can_delete,
            row_filter=permission.row_filter,
            columns=columns_by_permission.get(
                permission.id,
                [],
            ),
        )
        for permission in permissions
    ]

    return items, total
