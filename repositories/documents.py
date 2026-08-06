import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.knowledge_base import (
    Document,
    DocumentChunk,
)


async def get_document_by_checksum(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    checksum_sha256: str,
) -> Document | None:
    result = await session.execute(
        select(Document).where(
            Document.tenant_id == tenant_id,
            Document.knowledge_base_id == knowledge_base_id,
            Document.checksum_sha256 == checksum_sha256,
        )
    )

    return result.scalar_one_or_none()


async def get_document_by_id(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
) -> Document | None:
    result = await session.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
            Document.knowledge_base_id == knowledge_base_id,
        )
    )

    return result.scalar_one_or_none()


async def create_document_record(
    *,
    session: AsyncSession,
    document: Document,
) -> Document:
    session.add(document)
    await session.commit()
    await session.refresh(document)

    return document


async def list_document_records(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    knowledge_base_id: uuid.UUID,
    offset: int,
    limit: int,
) -> tuple[list[Document], int]:
    items_result = await session.execute(
        select(Document)
        .where(
            Document.tenant_id == tenant_id,
            Document.knowledge_base_id == knowledge_base_id,
        )
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    total_result = await session.execute(
        select(func.count(Document.id)).where(
            Document.tenant_id == tenant_id,
            Document.knowledge_base_id == knowledge_base_id,
        )
    )

    return (
        list(items_result.scalars().all()),
        total_result.scalar_one(),
    )


async def delete_document_record(
    *,
    session: AsyncSession,
    document: Document,
) -> None:
    await session.delete(document)
    await session.commit()


async def save_document_record(
    *,
    session: AsyncSession,
    document: Document,
) -> Document:
    await session.commit()
    await session.refresh(document)

    return document


async def replace_document_chunks(
    *,
    session: AsyncSession,
    document: Document,
    chunks: list[DocumentChunk],
) -> None:
    await session.execute(
        delete(DocumentChunk).where(
            DocumentChunk.tenant_id == document.tenant_id,
            DocumentChunk.knowledge_base_id == document.knowledge_base_id,
            DocumentChunk.document_id == document.id,
        )
    )

    session.add_all(chunks)
    await session.commit()


async def count_document_chunks(
    *,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    document_id: uuid.UUID,
) -> int:
    result = await session.execute(
        select(func.count(DocumentChunk.id)).where(
            DocumentChunk.tenant_id == tenant_id,
            DocumentChunk.document_id == document_id,
        )
    )

    return result.scalar_one()
