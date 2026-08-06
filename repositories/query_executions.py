from sqlalchemy.ext.asyncio import AsyncSession

from models.conversation import QueryExecution


async def create_query_execution_record(
    *,
    session: AsyncSession,
    query_execution: QueryExecution,
) -> QueryExecution:
    session.add(query_execution)
    await session.flush()
    await session.refresh(query_execution)

    return query_execution


async def save_query_execution_record(
    *,
    session: AsyncSession,
    query_execution: QueryExecution,
) -> QueryExecution:
    await session.flush()
    await session.refresh(query_execution)

    return query_execution
