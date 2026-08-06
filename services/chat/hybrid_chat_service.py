import json
import uuid
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from models.conversation import (
    Message,
    MessageCitation,
    QueryExecution,
)
from models.user import User
from repositories.messages import (
    create_hybrid_message_exchange,
)
from schemas.hybrid_chat import HybridMessageCreate
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
from services.document.retrieval_service import (
    RetrievedDocumentChunk,
    retrieve_relevant_chunks,
)


@dataclass(slots=True)
class HybridMessageExchange:
    user_message: MessageResponse
    assistant_message: MessageResponse


def build_hybrid_answer(
    *,
    columns: list[str],
    rows: list[dict[str, Any]],
    matches: list[RetrievedDocumentChunk],
) -> str:
    if rows:
        database_section = json.dumps(
            rows,
            ensure_ascii=False,
            indent=2,
        )
    else:
        database_section = "No database rows were returned."

    document_parts: list[str] = []

    for citation_index, match in enumerate(
        matches,
        start=1,
    ):
        normalized_content = " ".join(match.content.split())

        document_parts.append(f"[D{citation_index}] {normalized_content}")

    document_section = (
        "\n\n".join(document_parts)
        if document_parts
        else "No relevant document chunks were found."
    )

    return (
        "Database results:\n\n"
        f"Columns: {', '.join(columns)}\n\n"
        f"{database_section}\n\n"
        "Relevant document evidence:\n\n"
        f"{document_section}\n\n"
        "This response combines only the secured database "
        "results and cited document evidence."
    )


def build_query_execution(
    *,
    current_user: User,
    conversation_id: uuid.UUID,
    connection_id: uuid.UUID,
    proposed_sql: str,
) -> QueryExecution:
    return QueryExecution(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        conversation_id=conversation_id,
        message_id=None,
        connection_id=connection_id,
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
        execution_metadata={
            "mode": "hybrid",
        },
    )


async def save_failed_execution(
    *,
    session: AsyncSession,
    query_execution: QueryExecution,
    status: str,
    error_code: str,
) -> None:
    query_execution.status = status
    query_execution.error_code = error_code

    session.add(query_execution)
    await session.commit()


async def create_hybrid_message(
    *,
    session: AsyncSession,
    current_user: User,
    conversation_id: uuid.UUID,
    request: HybridMessageCreate,
) -> HybridMessageExchange:
    conversation = await get_conversation(
        session=session,
        current_user=current_user,
        conversation_id=conversation_id,
    )

    if conversation.mode != "hybrid":
        raise UnsupportedConversationModeError(
            "This endpoint supports hybrid conversations only."
        )

    if conversation.connection_id is None:
        raise UnsupportedConversationModeError(
            "The hybrid conversation has no database connection."
        )

    if conversation.knowledge_base_id is None:
        raise UnsupportedConversationModeError(
            "The hybrid conversation has no knowledge base."
        )

    normalized_question = request.content.strip()
    proposed_sql = request.proposed_sql.strip()
    started_at = perf_counter()

    query_execution = build_query_execution(
        current_user=current_user,
        conversation_id=conversation.id,
        connection_id=conversation.connection_id,
        proposed_sql=proposed_sql,
    )

    try:
        secure_execution = await run_secure_query(
            session=session,
            current_user=current_user,
            connection_id=conversation.connection_id,
            proposed_sql=proposed_sql,
        )
    except QuerySecurityError:
        await save_failed_execution(
            session=session,
            query_execution=query_execution,
            status="rejected",
            error_code="query_security_rejected",
        )
        raise
    except QueryExecutionTimeoutError:
        await save_failed_execution(
            session=session,
            query_execution=query_execution,
            status="failed",
            error_code="query_timeout",
        )
        raise
    except QueryResultTooLargeError:
        await save_failed_execution(
            session=session,
            query_execution=query_execution,
            status="failed",
            error_code="result_too_large",
        )
        raise
    except QueryExecutionError:
        await save_failed_execution(
            session=session,
            query_execution=query_execution,
            status="failed",
            error_code="query_execution_failed",
        )
        raise

    matches = await retrieve_relevant_chunks(
        session=session,
        current_user=current_user,
        knowledge_base_id=conversation.knowledge_base_id,
        query=normalized_question,
        top_k=request.top_k,
        minimum_similarity=request.minimum_similarity,
    )

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
        "mode": "hybrid",
        "truncated": execution.truncated,
        "retrieved_chunk_count": len(matches),
    }

    assistant_content = build_hybrid_answer(
        columns=execution.columns,
        rows=execution.rows,
        matches=matches,
    )

    latency_ms = int((perf_counter() - started_at) * 1000)

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
            "mode": "hybrid",
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
        latency_ms=latency_ms,
        message_metadata={
            "mode": "hybrid",
            "database_row_count": execution.row_count,
            "retrieved_chunk_count": len(matches),
            "masked": True,
        },
    )

    citations = [
        MessageCitation(
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
    ]

    citations.extend(
        MessageCitation(
            tenant_id=current_user.tenant_id,
            message_id=uuid.uuid4(),
            citation_type="document",
            document_id=match.document_id,
            document_chunk_id=match.chunk_id,
            query_execution_id=None,
            source_name=match.document_name,
            excerpt=match.content,
            page_number=match.page_number,
            section_title=match.section_title,
            similarity_score=match.similarity_score,
            citation_metadata={
                "chunk_index": match.chunk_index,
                "knowledge_base_id": str(conversation.knowledge_base_id),
            },
        )
        for match in matches
    )

    (
        saved_user_message,
        saved_assistant_message,
        _,
        saved_citations,
    ) = await create_hybrid_message_exchange(
        session=session,
        user_message=user_message,
        assistant_message=assistant_message,
        query_execution=query_execution,
        citations=citations,
    )

    return HybridMessageExchange(
        user_message=message_to_response(
            message=saved_user_message,
        ),
        assistant_message=message_to_response(
            message=saved_assistant_message,
            citations=saved_citations,
        ),
    )
