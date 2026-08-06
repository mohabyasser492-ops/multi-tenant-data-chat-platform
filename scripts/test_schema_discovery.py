import asyncio
import uuid

from sqlalchemy import select

from db.session import AsyncSessionFactory, engine
from models.database_connection import DatabaseConnection
from services.database.schema_discovery import (
    discover_database_schema,
)

CONNECTION_ID = uuid.UUID("a0d6485c-3e94-4ec6-860a-f1fdf25161b5")


async def test_schema_discovery() -> None:
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(DatabaseConnection).where(DatabaseConnection.id == CONNECTION_ID)
        )
        connection = result.scalar_one_or_none()

        if connection is None:
            print("Stored database connection was not found.")
            return

        discovery = await discover_database_schema(connection)

        print(f"Schemas discovered: {discovery.schema_count}")
        print(f"Tables discovered: {discovery.table_count}")
        print(f"Columns discovered: {discovery.column_count}")
        print()

        for schema in discovery.schemas:
            print(f"Schema: {schema.schema_name}")

            for table in schema.tables:
                print(f"  Table: {table.table_name} ({table.table_type})")
                print(f"    Primary key columns: {table.primary_key_columns}")

                for column in table.columns:
                    print(f"    Column: {column.column_name} [{column.data_type}]")


async def main() -> None:
    try:
        await test_schema_discovery()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
