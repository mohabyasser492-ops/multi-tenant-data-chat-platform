import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database_schema import (
    DatabaseColumn,
    DatabaseSchema,
    DatabaseTable,
)
from models.role import UserRole
from models.table_permission import (
    ColumnPermission,
    TablePermission,
)


async def get_user_role_ids(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
) -> list[uuid.UUID]:
    result = await session.execute(
        select(UserRole.role_id).where(
            UserRole.user_id == user_id,
        )
    )

    return list(result.scalars().all())


async def get_effective_table_permissions(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    connection_id: uuid.UUID,
    role_ids: list[uuid.UUID],
) -> list[
    tuple[
        TablePermission,
        DatabaseTable,
        DatabaseSchema,
    ]
]:
    subject_conditions = [
        TablePermission.user_id == user_id,
    ]

    if role_ids:
        subject_conditions.append(TablePermission.role_id.in_(role_ids))

    result = await session.execute(
        select(
            TablePermission,
            DatabaseTable,
            DatabaseSchema,
        )
        .join(
            DatabaseTable,
            TablePermission.table_id == DatabaseTable.id,
        )
        .join(
            DatabaseSchema,
            DatabaseTable.schema_id == DatabaseSchema.id,
        )
        .where(
            TablePermission.tenant_id == tenant_id,
            TablePermission.connection_id == connection_id,
            DatabaseTable.tenant_id == tenant_id,
            DatabaseTable.connection_id == connection_id,
            DatabaseTable.is_enabled.is_(True),
            DatabaseSchema.tenant_id == tenant_id,
            DatabaseSchema.connection_id == connection_id,
            or_(*subject_conditions),
        )
        .order_by(
            DatabaseSchema.schema_name,
            DatabaseTable.table_name,
        )
    )

    return list(result.all())


async def get_effective_column_permissions(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    table_permission_ids: list[uuid.UUID],
) -> list[
    tuple[
        ColumnPermission,
        DatabaseColumn,
    ]
]:
    if not table_permission_ids:
        return []

    result = await session.execute(
        select(
            ColumnPermission,
            DatabaseColumn,
        )
        .join(
            DatabaseColumn,
            ColumnPermission.column_id == DatabaseColumn.id,
        )
        .where(
            ColumnPermission.table_permission_id.in_(table_permission_ids),
            DatabaseColumn.tenant_id == tenant_id,
        )
        .order_by(
            DatabaseColumn.table_id,
            DatabaseColumn.ordinal_position,
        )
    )

    return list(result.all())
