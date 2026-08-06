import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database_connection import DatabaseConnection


async def get_connection_by_name(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    name: str,
) -> DatabaseConnection | None:
    result = await session.execute(
        select(DatabaseConnection).where(
            DatabaseConnection.tenant_id == tenant_id,
            DatabaseConnection.name == name,
        )
    )

    return result.scalar_one_or_none()


async def get_connection_by_id(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID,
) -> DatabaseConnection | None:
    result = await session.execute(
        select(DatabaseConnection).where(
            DatabaseConnection.id == connection_id,
            DatabaseConnection.tenant_id == tenant_id,
        )
    )

    return result.scalar_one_or_none()


async def create_connection(
    *,
    session: AsyncSession,
    connection: DatabaseConnection,
) -> DatabaseConnection:
    session.add(connection)
    await session.commit()
    await session.refresh(connection)

    return connection


async def list_connections(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    offset: int = 0,
    limit: int = 100,
) -> tuple[list[DatabaseConnection], int]:
    items_result = await session.execute(
        select(DatabaseConnection)
        .where(
            DatabaseConnection.tenant_id == tenant_id,
        )
        .order_by(DatabaseConnection.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    total_result = await session.execute(
        select(func.count(DatabaseConnection.id)).where(
            DatabaseConnection.tenant_id == tenant_id,
        )
    )

    items = list(items_result.scalars().all())
    total = total_result.scalar_one()

    return items, total


async def save_connection(
    *,
    session: AsyncSession,
    connection: DatabaseConnection,
) -> DatabaseConnection:
    await session.commit()
    await session.refresh(connection)

    return connection


async def delete_connection(
    *,
    session: AsyncSession,
    connection: DatabaseConnection,
) -> None:
    await session.delete(connection)
    await session.commit()
