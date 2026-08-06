import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError

from app.dependencies import CurrentUser, DatabaseSession
from schemas.message import (
    ConversationMessageExchangeResponse,
    MessageCreate,
    MessageListResponse,
)
from services.chat.conversation_service import (
    ConversationNotFoundError,
)
from services.chat.document_chat_service import (
    UnsupportedConversationModeError,
    create_document_message,
    get_conversation_messages,
)
from services.document.knowledge_base_service import (
    KnowledgeBaseNotFoundError,
)
from services.document.retrieval_service import (
    DocumentRetrievalError,
)

router = APIRouter(
    prefix="/conversations",
    tags=["Conversation Messages"],
)


@router.post(
    "/{conversation_id}/messages",
    response_model=ConversationMessageExchangeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a retrieval-backed document message",
)
async def create_message_endpoint(
    conversation_id: uuid.UUID,
    request: MessageCreate,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> ConversationMessageExchangeResponse:
    try:
        exchange = await create_document_message(
            session=session,
            current_user=current_user,
            conversation_id=conversation_id,
            request=request,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation was not found.",
        ) from exc
    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base was not found.",
        ) from exc
    except UnsupportedConversationModeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except DocumentRetrievalError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except SQLAlchemyError as exc:
        await session.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The conversation message could not be saved.",
        ) from exc

    return ConversationMessageExchangeResponse(
        user_message=exchange.user_message,
        assistant_message=exchange.assistant_message,
    )


@router.get(
    "/{conversation_id}/messages",
    response_model=MessageListResponse,
    status_code=status.HTTP_200_OK,
    summary="List messages and citations in a conversation",
)
async def list_messages_endpoint(
    conversation_id: uuid.UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MessageListResponse:
    try:
        messages, total = await get_conversation_messages(
            session=session,
            current_user=current_user,
            conversation_id=conversation_id,
            offset=offset,
            limit=limit,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation was not found.",
        ) from exc

    return MessageListResponse(
        items=messages,
        total=total,
    )
