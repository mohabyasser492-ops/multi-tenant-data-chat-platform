import asyncio

from sqlalchemy import text

from db.session import engine


async def test_database() -> None:
    async with engine.connect() as connection:
        result = await connection.execute(
            text("SELECT current_database(), current_user")
        )
        database_name, database_user = result.one()

        print(f"Database: {database_name}")
        print(f"User: {database_user}")
        print("Database connection successful")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test_database())
