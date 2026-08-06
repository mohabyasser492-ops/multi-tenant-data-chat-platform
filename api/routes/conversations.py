import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import CurrentUser, DatabaseSession
from schemas.conversation import (
    ConversationCreate,
    ConversationListResponse,
    ConversationResponse,
)
from services.chat.conversation_service import (
    ConversationNotFoundError,
    create_conversation,
    get_conversation,
    list_conversations,
)
from services.database.connection_service import (
    DatabaseConnectionNotFoundError,
)
from services.document.knowledge_base_service import (
    KnowledgeBaseNotFoundError,
)

router = APIRouter(
    prefix="/conversations",
    tags=["Conversations"],
)


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a conversation",
)
async def create_conversation_endpoint(
    request: ConversationCreate,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> ConversationResponse:
    try:
        conversation = await create_conversation(
            session=session,
            current_user=current_user,
            request=request,
        )
    except DatabaseConnectionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database connection was not found.",
        ) from exc
    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base was not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return ConversationResponse.model_validate(conversation)


@router.get(
    "",
    response_model=ConversationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List conversations for the authenticated user",
)
async def list_conversations_endpoint(
    session: DatabaseSession,
    current_user: CurrentUser,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ConversationListResponse:
    conversations, total = await list_conversations(
        session=session,
        current_user=current_user,
        offset=offset,
        limit=limit,
    )

    return ConversationListResponse(
        items=[
            ConversationResponse.model_validate(conversation)
            for conversation in conversations
        ],
        total=total,
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a conversation",
)
async def get_conversation_endpoint(
    conversation_id: uuid.UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> ConversationResponse:
    try:
        conversation = await get_conversation(
            session=session,
            current_user=current_user,
            conversation_id=conversation_id,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation was not found.",
        ) from exc

    return ConversationResponse.model_validate(conversation)
