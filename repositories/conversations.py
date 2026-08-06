import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.conversation import Conversation


async def create_conversation_record(
    *,
    session: AsyncSession,
    conversation: Conversation,
) -> Conversation:
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)

    return conversation


async def get_conversation_by_id(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> Conversation | None:
    result = await session.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == tenant_id,
            Conversation.user_id == user_id,
        )
    )

    return result.scalar_one_or_none()


async def list_conversation_records(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    offset: int,
    limit: int,
) -> tuple[list[Conversation], int]:
    filters = (
        Conversation.tenant_id == tenant_id,
        Conversation.user_id == user_id,
    )

    items_result = await session.execute(
        select(Conversation)
        .where(*filters)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )

    total_result = await session.execute(
        select(func.count(Conversation.id)).where(*filters)
    )

    return (
        list(items_result.scalars().all()),
        total_result.scalar_one(),
    )
