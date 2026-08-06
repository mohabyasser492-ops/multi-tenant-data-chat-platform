import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.table_permission import (
    ColumnPermission,
    TablePermission,
)


async def find_existing_table_permission(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    table_id: uuid.UUID,
    role_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
) -> TablePermission | None:
    subject_condition = or_(
        (TablePermission.role_id == role_id if role_id is not None else False),
        (TablePermission.user_id == user_id if user_id is not None else False),
    )

    result = await session.execute(
        select(TablePermission).where(
            TablePermission.tenant_id == tenant_id,
            TablePermission.table_id == table_id,
            subject_condition,
        )
    )

    return result.scalar_one_or_none()


async def create_table_permission(
    *,
    session: AsyncSession,
    permission: TablePermission,
    column_permissions: list[ColumnPermission],
) -> TablePermission:
    session.add(permission)
    await session.flush()

    for column_permission in column_permissions:
        column_permission.table_permission_id = permission.id
        session.add(column_permission)

    await session.commit()
    await session.refresh(permission)

    return permission


async def list_table_permissions(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID | None = None,
    table_id: uuid.UUID | None = None,
) -> tuple[list[TablePermission], int]:
    query = select(TablePermission).where(
        TablePermission.tenant_id == tenant_id,
    )
    count_query = select(func.count(TablePermission.id)).where(
        TablePermission.tenant_id == tenant_id,
    )

    if connection_id is not None:
        query = query.where(
            TablePermission.connection_id == connection_id,
        )
        count_query = count_query.where(
            TablePermission.connection_id == connection_id,
        )

    if table_id is not None:
        query = query.where(
            TablePermission.table_id == table_id,
        )
        count_query = count_query.where(
            TablePermission.table_id == table_id,
        )

    query = query.order_by(
        TablePermission.created_at.desc(),
    )

    items_result = await session.execute(query)
    total_result = await session.execute(count_query)

    return (
        list(items_result.scalars().all()),
        total_result.scalar_one(),
    )


async def list_column_permissions(
    *,
    session: AsyncSession,
    table_permission_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[ColumnPermission]]:
    if not table_permission_ids:
        return {}

    result = await session.execute(
        select(ColumnPermission)
        .where(ColumnPermission.table_permission_id.in_(table_permission_ids))
        .order_by(
            ColumnPermission.table_permission_id,
            ColumnPermission.column_id,
        )
    )

    columns_by_permission: dict[
        uuid.UUID,
        list[ColumnPermission],
    ] = {}

    for column_permission in result.scalars().all():
        columns_by_permission.setdefault(
            column_permission.table_permission_id,
            [],
        ).append(column_permission)

    return columns_by_permission
