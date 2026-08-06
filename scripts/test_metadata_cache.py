import asyncio
import uuid

from sqlalchemy import func, select

from db.session import AsyncSessionFactory, engine
from models.database_connection import DatabaseConnection
from models.database_schema import (
    DatabaseColumn,
    DatabaseSchema,
    DatabaseTable,
)
from services.database.metadata_cache import (
    cache_discovered_metadata,
)
from services.database.schema_discovery import (
    discover_database_schema,
)

CONNECTION_ID = uuid.UUID("a0d6485c-3e94-4ec6-860a-f1fdf25161b5")


async def run_metadata_cache_test() -> None:
    async with AsyncSessionFactory() as session:
        connection_result = await session.execute(
            select(DatabaseConnection).where(DatabaseConnection.id == CONNECTION_ID)
        )
        connection = connection_result.scalar_one_or_none()

        if connection is None:
            print("Stored database connection was not found.")
            return

        discovery = await discover_database_schema(connection)

        schema_count, table_count, column_count = await cache_discovered_metadata(
            session=session,
            tenant_id=connection.tenant_id,
            connection_id=connection.id,
            discovery=discovery,
        )

        print(f"Cached schemas: {schema_count}")
        print(f"Cached tables: {table_count}")
        print(f"Cached columns: {column_count}")

        stored_schema_count = await session.scalar(
            select(func.count(DatabaseSchema.id)).where(
                DatabaseSchema.tenant_id == connection.tenant_id,
                DatabaseSchema.connection_id == connection.id,
            )
        )

        stored_table_count = await session.scalar(
            select(func.count(DatabaseTable.id)).where(
                DatabaseTable.tenant_id == connection.tenant_id,
                DatabaseTable.connection_id == connection.id,
            )
        )

        stored_column_count = await session.scalar(
            select(func.count(DatabaseColumn.id))
            .join(
                DatabaseTable,
                DatabaseColumn.table_id == DatabaseTable.id,
            )
            .where(
                DatabaseColumn.tenant_id == connection.tenant_id,
                DatabaseTable.connection_id == connection.id,
            )
        )

        print()
        print(f"Stored schemas: {stored_schema_count}")
        print(f"Stored tables: {stored_table_count}")
        print(f"Stored columns: {stored_column_count}")


async def main() -> None:
    try:
        await run_metadata_cache_test()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
