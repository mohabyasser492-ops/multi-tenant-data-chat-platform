import json
import uuid
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from models.conversation import (
    Message,
    MessageCitation,
    QueryExecution,
)
from models.user import User
from repositories.messages import (
    create_database_message_exchange,
)
from schemas.database_chat import DatabaseMessageCreate
from schemas.message import MessageResponse
from services.chat.conversation_service import (
    get_conversation,
)
from services.chat.document_chat_service import (
    UnsupportedConversationModeError,
    estimate_message_tokens,
    message_to_response,
)
from services.database.query_executor import (
    QueryExecutionError,
    QueryExecutionTimeoutError,
    QueryResultTooLargeError,
)
from services.database.query_security_service import (
    QuerySecurityError,
)
from services.database.secure_query_service import (
    run_secure_query,
)


@dataclass(slots=True)
class DatabaseMessageExchange:
    user_message: MessageResponse
    assistant_message: MessageResponse


def build_database_answer(
    *,
    columns: list[str],
    rows: list[dict[str, Any]],
    row_count: int,
) -> str:
    if not rows:
        return "The secured database query completed successfully but returned no rows."

    result_json = json.dumps(
        rows,
        ensure_ascii=False,
        indent=2,
    )

    return (
        f"The secured query returned {row_count} row(s).\n\n"
        f"Columns: {', '.join(columns)}\n\n"
        f"Results:\n{result_json}"
    )


async def create_database_message(
    *,
    session: AsyncSession,
    current_user: User,
    conversation_id: uuid.UUID,
    request: DatabaseMessageCreate,
) -> DatabaseMessageExchange:
    conversation = await get_conversation(
        session=session,
        current_user=current_user,
        conversation_id=conversation_id,
    )

    if conversation.mode != "database":
        raise UnsupportedConversationModeError(
            "This endpoint supports database conversations only."
        )

    if conversation.connection_id is None:
        raise UnsupportedConversationModeError(
            "The database conversation has no connection."
        )

    normalized_question = request.content.strip()
    proposed_sql = request.proposed_sql.strip()
    started_at = perf_counter()

    query_execution = QueryExecution(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        conversation_id=conversation.id,
        message_id=None,
        connection_id=conversation.connection_id,
        proposed_sql=proposed_sql,
        secured_sql=None,
        status="pending",
        error_code=None,
        row_count=None,
        result_size_bytes=None,
        execution_time_ms=None,
        applied_limit=None,
        row_filters_applied=False,
        referenced_tables=[],
        referenced_columns=[],
        execution_metadata={},
    )

    try:
        secure_execution = await run_secure_query(
            session=session,
            current_user=current_user,
            connection_id=conversation.connection_id,
            proposed_sql=proposed_sql,
        )
    except QuerySecurityError:
        query_execution.status = "rejected"
        query_execution.error_code = "query_security_rejected"

        session.add(query_execution)
        await session.commit()
        raise
    except QueryExecutionTimeoutError:
        query_execution.status = "failed"
        query_execution.error_code = "query_timeout"

        session.add(query_execution)
        await session.commit()
        raise
    except QueryResultTooLargeError:
        query_execution.status = "failed"
        query_execution.error_code = "result_too_large"

        session.add(query_execution)
        await session.commit()
        raise
    except QueryExecutionError:
        query_execution.status = "failed"
        query_execution.error_code = "query_execution_failed"

        session.add(query_execution)
        await session.commit()
        raise

    security = secure_execution.security
    execution = secure_execution.execution

    query_execution.secured_sql = security.sql
    query_execution.status = "completed"
    query_execution.row_count = execution.row_count
    query_execution.result_size_bytes = execution.result_size_bytes
    query_execution.execution_time_ms = execution.execution_time_ms
    query_execution.applied_limit = security.applied_limit
    query_execution.row_filters_applied = security.row_filters_applied
    query_execution.referenced_tables = security.referenced_tables
    query_execution.referenced_columns = security.referenced_columns
    query_execution.execution_metadata = {
        "truncated": execution.truncated,
    }

    assistant_content = build_database_answer(
        columns=execution.columns,
        rows=execution.rows,
        row_count=execution.row_count,
    )

    total_latency_ms = int((perf_counter() - started_at) * 1000)

    user_message = Message(
        tenant_id=current_user.tenant_id,
        conversation_id=conversation.id,
        user_id=current_user.id,
        role="user",
        content=normalized_question,
        status="completed",
        token_count=estimate_message_tokens(normalized_question),
        latency_ms=None,
        message_metadata={
            "mode": "database",
        },
    )

    assistant_message = Message(
        tenant_id=current_user.tenant_id,
        conversation_id=conversation.id,
        user_id=None,
        role="assistant",
        content=assistant_content,
        status="completed",
        token_count=estimate_message_tokens(assistant_content),
        latency_ms=total_latency_ms,
        message_metadata={
            "mode": "database",
            "row_count": execution.row_count,
            "columns": execution.columns,
            "masked": True,
        },
    )

    citation = MessageCitation(
        tenant_id=current_user.tenant_id,
        message_id=uuid.uuid4(),
        citation_type="database",
        document_id=None,
        document_chunk_id=None,
        query_execution_id=None,
        source_name=", ".join(security.referenced_tables),
        excerpt=security.sql,
        page_number=None,
        section_title=None,
        similarity_score=None,
        citation_metadata={
            "row_count": execution.row_count,
            "referenced_columns": (security.referenced_columns),
            "applied_limit": security.applied_limit,
            "row_filters_applied": (security.row_filters_applied),
        },
    )

    try:
        (
            saved_user_message,
            saved_assistant_message,
            _,
            saved_citation,
        ) = await create_database_message_exchange(
            session=session,
            user_message=user_message,
            assistant_message=assistant_message,
            query_execution=query_execution,
            citation=citation,
        )
    except SQLAlchemyError:
        await session.rollback()
        raise

    return DatabaseMessageExchange(
        user_message=message_to_response(
            message=saved_user_message,
        ),
        assistant_message=message_to_response(
            message=saved_assistant_message,
            citations=[saved_citation],
        ),
    )
