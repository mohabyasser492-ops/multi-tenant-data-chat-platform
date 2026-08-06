import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from models.conversation import Conversation
from models.user import User
from repositories.conversations import (
    create_conversation_record,
    get_conversation_by_id,
    list_conversation_records,
)
from schemas.conversation import (
    ConversationCreate,
    ConversationMode,
)
from services.database.connection_service import (
    get_database_connection,
)
from services.document.knowledge_base_service import (
    get_knowledge_base,
)


class ConversationNotFoundError(LookupError):
    """Raised when a conversation is unavailable to the user."""


async def validate_conversation_sources(
    *,
    session: AsyncSession,
    current_user: User,
    request: ConversationCreate,
) -> None:
    if request.connection_id is not None:
        await get_database_connection(
            session=session,
            current_user=current_user,
            connection_id=request.connection_id,
        )

    if request.knowledge_base_id is not None:
        knowledge_base = await get_knowledge_base(
            session=session,
            current_user=current_user,
            knowledge_base_id=request.knowledge_base_id,
        )

        if not knowledge_base.is_active:
            raise ValueError("The selected knowledge base is disabled.")

    if (
        request.mode == ConversationMode.DATABASE
        and request.knowledge_base_id is not None
    ):
        raise ValueError("Database conversations cannot specify a knowledge base.")

    if request.mode == ConversationMode.DOCUMENT and request.connection_id is not None:
        raise ValueError("Document conversations cannot specify a database connection.")


async def create_conversation(
    *,
    session: AsyncSession,
    current_user: User,
    request: ConversationCreate,
) -> Conversation:
    await validate_conversation_sources(
        session=session,
        current_user=current_user,
        request=request,
    )

    conversation = Conversation(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        connection_id=request.connection_id,
        knowledge_base_id=request.knowledge_base_id,
        title=request.title.strip(),
        mode=request.mode.value,
        status="active",
        conversation_metadata=request.metadata,
        is_archived=False,
    )

    return await create_conversation_record(
        session=session,
        conversation=conversation,
    )


async def list_conversations(
    *,
    session: AsyncSession,
    current_user: User,
    offset: int,
    limit: int,
) -> tuple[list[Conversation], int]:
    return await list_conversation_records(
        session=session,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        offset=offset,
        limit=limit,
    )


async def get_conversation(
    *,
    session: AsyncSession,
    current_user: User,
    conversation_id: uuid.UUID,
) -> Conversation:
    conversation = await get_conversation_by_id(
        session=session,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        conversation_id=conversation_id,
    )

    if conversation is None:
        raise ConversationNotFoundError("Conversation was not found.")

    return conversation
