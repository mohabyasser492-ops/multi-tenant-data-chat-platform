import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.conversation import (
    Message,
    MessageCitation,
    QueryExecution,
)


async def create_message_record(
    *,
    session: AsyncSession,
    message: Message,
) -> Message:
    session.add(message)
    await session.flush()
    await session.refresh(message)

    return message


async def create_message_exchange(
    *,
    session: AsyncSession,
    user_message: Message,
    assistant_message: Message,
    citations: list[MessageCitation],
) -> tuple[
    Message,
    Message,
    list[MessageCitation],
]:
    session.add(user_message)
    await session.flush()

    session.add(assistant_message)
    await session.flush()

    for citation in citations:
        citation.message_id = assistant_message.id
        session.add(citation)

    await session.commit()
    await session.refresh(user_message)
    await session.refresh(assistant_message)

    for citation in citations:
        await session.refresh(citation)

    return (
        user_message,
        assistant_message,
        citations,
    )


async def list_message_records(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    conversation_id: uuid.UUID,
    offset: int,
    limit: int,
) -> tuple[list[Message], int]:
    filters = (
        Message.tenant_id == tenant_id,
        Message.conversation_id == conversation_id,
    )

    items_result = await session.execute(
        select(Message)
        .where(*filters)
        .order_by(Message.created_at)
        .offset(offset)
        .limit(limit)
    )

    total_result = await session.execute(select(func.count(Message.id)).where(*filters))

    return (
        list(items_result.scalars().all()),
        total_result.scalar_one(),
    )


async def list_message_citations(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    message_ids: list[uuid.UUID],
) -> dict[
    uuid.UUID,
    list[MessageCitation],
]:
    if not message_ids:
        return {}

    result = await session.execute(
        select(MessageCitation)
        .where(
            MessageCitation.tenant_id == tenant_id,
            MessageCitation.message_id.in_(message_ids),
        )
        .order_by(
            MessageCitation.message_id,
            MessageCitation.created_at,
        )
    )

    citations_by_message: dict[
        uuid.UUID,
        list[MessageCitation],
    ] = {}

    for citation in result.scalars().all():
        citations_by_message.setdefault(
            citation.message_id,
            [],
        ).append(citation)

    return citations_by_message


async def create_database_message_exchange(
    *,
    session: AsyncSession,
    user_message: Message,
    assistant_message: Message,
    query_execution: "QueryExecution",
    citation: MessageCitation,
) -> tuple[
    Message,
    Message,
    "QueryExecution",
    MessageCitation,
]:
    session.add(user_message)
    await session.flush()

    session.add(assistant_message)
    await session.flush()

    query_execution.message_id = assistant_message.id
    session.add(query_execution)
    await session.flush()

    citation.message_id = assistant_message.id
    citation.query_execution_id = query_execution.id
    session.add(citation)

    await session.commit()

    await session.refresh(user_message)
    await session.refresh(assistant_message)
    await session.refresh(query_execution)
    await session.refresh(citation)

    return (
        user_message,
        assistant_message,
        query_execution,
        citation,
    )
