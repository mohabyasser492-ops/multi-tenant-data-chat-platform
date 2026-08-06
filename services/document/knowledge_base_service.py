import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from models.knowledge_base import KnowledgeBase
from models.user import User
from repositories.knowledge_bases import (
    create_knowledge_base_record,
    get_knowledge_base_by_id,
    get_knowledge_base_by_name,
    list_knowledge_base_records,
)
from schemas.knowledge_base import KnowledgeBaseCreate
from services.database.connection_service import (
    require_tenant_administrator,
)


class KnowledgeBaseNotFoundError(LookupError):
    """Raised when a knowledge base is unavailable to the tenant."""


class DuplicateKnowledgeBaseNameError(ValueError):
    """Raised when a tenant already uses a knowledge-base name."""


async def create_knowledge_base(
    *,
    session: AsyncSession,
    current_user: User,
    request: KnowledgeBaseCreate,
) -> KnowledgeBase:
    require_tenant_administrator(current_user)

    normalized_name = request.name.strip()

    existing = await get_knowledge_base_by_name(
        session=session,
        tenant_id=current_user.tenant_id,
        name=normalized_name,
    )

    if existing is not None:
        raise DuplicateKnowledgeBaseNameError(
            "A knowledge base with this name already exists."
        )

    normalized_description = (
        request.description.strip() if request.description else None
    )

    knowledge_base = KnowledgeBase(
        tenant_id=current_user.tenant_id,
        created_by=current_user.id,
        name=normalized_name,
        description=normalized_description,
        embedding_model=settings.embedding_model,
        embedding_dimension=settings.embedding_dimension,
        chunk_size=request.chunk_size,
        chunk_overlap=request.chunk_overlap,
        settings_data=request.settings,
        is_active=True,
    )

    return await create_knowledge_base_record(
        session=session,
        knowledge_base=knowledge_base,
    )


async def list_knowledge_bases(
    *,
    session: AsyncSession,
    current_user: User,
    offset: int,
    limit: int,
) -> tuple[list[KnowledgeBase], int]:
    return await list_knowledge_base_records(
        session=session,
        tenant_id=current_user.tenant_id,
        offset=offset,
        limit=limit,
    )


async def get_knowledge_base(
    *,
    session: AsyncSession,
    current_user: User,
    knowledge_base_id: uuid.UUID,
) -> KnowledgeBase:
    knowledge_base = await get_knowledge_base_by_id(
        session=session,
        tenant_id=current_user.tenant_id,
        knowledge_base_id=knowledge_base_id,
    )

    if knowledge_base is None:
        raise KnowledgeBaseNotFoundError("Knowledge base was not found.")

    return knowledge_base
