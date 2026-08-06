import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from models.database_connection import DatabaseConnection
from models.user import User
from repositories.connections import save_connection
from services.database.connection_service import (
    get_database_connection,
    require_tenant_administrator,
)
from services.database.metadata_cache import (
    cache_discovered_metadata,
)
from services.database.schema_discovery import (
    SchemaDiscoveryError,
    discover_database_schema,
)


@dataclass(slots=True)
class SchemaSyncResult:
    connection: DatabaseConnection
    schema_count: int
    table_count: int
    column_count: int
    synchronized_at: datetime


async def synchronize_database_schema(
    *,
    session: AsyncSession,
    current_user: User,
    connection_id: uuid.UUID,
) -> SchemaSyncResult:
    require_tenant_administrator(current_user)

    connection = await get_database_connection(
        session=session,
        current_user=current_user,
        connection_id=connection_id,
    )

    connection.schema_sync_status = "processing"
    connection.last_schema_sync_at = None

    await save_connection(
        session=session,
        connection=connection,
    )

    try:
        discovery = await discover_database_schema(
            connection,
            timeout_seconds=settings.sql_timeout_seconds,
        )

        schema_count, table_count, column_count = (
            await cache_discovered_metadata(
                session=session,
                tenant_id=current_user.tenant_id,
                connection_id=connection.id,
                discovery=discovery,
            )
        )
    except SchemaDiscoveryError:
        connection.schema_sync_status = "failed"

        await save_connection(
            session=session,
            connection=connection,
        )

        raise

    synchronized_at = datetime.now(UTC)

    connection.schema_sync_status = "completed"
    connection.last_schema_sync_at = synchronized_at

    saved_connection = await save_connection(
        session=session,
        connection=connection,
    )

    return SchemaSyncResult(
        connection=saved_connection,
        schema_count=schema_count,
        table_count=table_count,
        column_count=column_count,
        synchronized_at=synchronized_at,
    )