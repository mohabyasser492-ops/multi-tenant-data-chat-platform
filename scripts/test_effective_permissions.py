import asyncio
import json
import uuid

from sqlalchemy import select

from db.session import AsyncSessionFactory, engine
from models.user import User
from services.database.effective_permission_service import (
    build_permission_filtered_schema,
)

CONNECTION_ID = uuid.UUID("a0d6485c-3e94-4ec6-860a-f1fdf25161b5")

ADMIN_EMAIL = "admin@example.com"


async def run_effective_permission_test() -> None:
    async with AsyncSessionFactory() as session:
        user_result = await session.execute(
            select(User).where(User.email == ADMIN_EMAIL)
        )
        user = user_result.scalar_one_or_none()

        if user is None:
            print("Test user was not found.")
            return

        allowed_schema = await build_permission_filtered_schema(
            session=session,
            current_user=user,
            connection_id=CONNECTION_ID,
        )

        print(
            json.dumps(
                allowed_schema.to_prompt_dict(),
                indent=2,
            )
        )


async def main() -> None:
    try:
        await run_effective_permission_test()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
