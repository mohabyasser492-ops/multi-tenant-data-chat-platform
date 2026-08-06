import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.knowledge_base import KnowledgeBase


async def get_knowledge_base_by_name(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    name: str,
) -> KnowledgeBase | None:
    result = await session.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.tenant_id == tenant_id,
            KnowledgeBase.name == name,
        )
    )

    return result.scalar_one_or_none()


async def get_knowledge_base_by_id(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
) -> KnowledgeBase | None:
    result = await session.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == knowledge_base_id,
            KnowledgeBase.tenant_id == tenant_id,
        )
    )

    return result.scalar_one_or_none()


async def create_knowledge_base_record(
    *,
    session: AsyncSession,
    knowledge_base: KnowledgeBase,
) -> KnowledgeBase:
    session.add(knowledge_base)
    await session.commit()
    await session.refresh(knowledge_base)

    return knowledge_base


async def list_knowledge_base_records(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    offset: int,
    limit: int,
) -> tuple[list[KnowledgeBase], int]:
    items_result = await session.execute(
        select(KnowledgeBase)
        .where(
            KnowledgeBase.tenant_id == tenant_id,
        )
        .order_by(
            KnowledgeBase.created_at.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    total_result = await session.execute(
        select(func.count(KnowledgeBase.id)).where(
            KnowledgeBase.tenant_id == tenant_id,
        )
    )

    return (
        list(items_result.scalars().all()),
        total_result.scalar_one(),
    )
