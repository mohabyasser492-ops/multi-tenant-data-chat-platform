import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from app.dependencies import CurrentUser, DatabaseSession
from schemas.database_chat import DatabaseMessageCreate
from schemas.message import (
    ConversationMessageExchangeResponse,
)
from services.chat.conversation_service import (
    ConversationNotFoundError,
)
from services.chat.database_chat_service import (
    create_database_message,
)
from services.chat.document_chat_service import (
    UnsupportedConversationModeError,
)
from services.database.query_executor import (
    QueryExecutionError,
    QueryExecutionTimeoutError,
    QueryResultTooLargeError,
)
from services.database.query_security_service import (
    QuerySecurityError,
)

router = APIRouter(
    prefix="/conversations",
    tags=["Database Chat"],
)


@router.post(
    "/{conversation_id}/database-messages",
    response_model=ConversationMessageExchangeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a secure database-chat message",
)
async def create_database_message_endpoint(
    conversation_id: uuid.UUID,
    request: DatabaseMessageCreate,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> ConversationMessageExchangeResponse:
    try:
        exchange = await create_database_message(
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
    except UnsupportedConversationModeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except QuerySecurityError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except QueryExecutionTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The secured query execution timed out.",
        ) from exc
    except QueryResultTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=("The query result exceeded the configured size limit."),
        ) from exc
    except QueryExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The secured query could not be executed.",
        ) from exc
    except SQLAlchemyError as exc:
        await session.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The database chat message could not be saved.",
        ) from exc

    return ConversationMessageExchangeResponse(
        user_message=exchange.user_message,
        assistant_message=exchange.assistant_message,
    )
