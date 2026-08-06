import uuid
from dataclasses import dataclass
from time import perf_counter

from sqlalchemy.ext.asyncio import AsyncSession

from models.conversation import (
    Message,
    MessageCitation,
)
from models.user import User
from repositories.messages import (
    create_message_exchange,
    list_message_citations,
    list_message_records,
)
from schemas.message import (
    MessageCitationResponse,
    MessageCreate,
    MessageResponse,
)
from services.chat.conversation_service import (
    get_conversation,
)
from services.document.retrieval_service import (
    RetrievedDocumentChunk,
    retrieve_relevant_chunks,
)


class UnsupportedConversationModeError(ValueError):
    """Raised when an endpoint cannot handle the conversation mode."""


class EmptyRetrievalResultError(LookupError):
    """Raised when no relevant document chunks are available."""


@dataclass(slots=True)
class DocumentMessageExchange:
    user_message: MessageResponse
    assistant_message: MessageResponse


def estimate_message_tokens(content: str) -> int:
    return max(
        1,
        len(content) // 4,
    )


def build_grounded_document_response(
    *,
    question: str,
    matches: list[RetrievedDocumentChunk],
) -> str:
    if not matches:
        return "I could not find relevant information in the selected knowledge base."

    answer_parts = ["Relevant information found in the selected documents:"]

    for citation_index, match in enumerate(
        matches,
        start=1,
    ):
        normalized_content = " ".join(match.content.split())

        answer_parts.append(f"[{citation_index}] {normalized_content}")

    answer_parts.append(
        "This response is based only on the cited document "
        "content retrieved for the question: "
        f"{question.strip()}"
    )

    return "\n\n".join(answer_parts)


def citation_to_response(
    citation: MessageCitation,
) -> MessageCitationResponse:
    return MessageCitationResponse.model_validate(citation)


def message_to_response(
    *,
    message: Message,
    citations: list[MessageCitation] | None = None,
) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        tenant_id=message.tenant_id,
        conversation_id=message.conversation_id,
        user_id=message.user_id,
        role=message.role,
        content=message.content,
        status=message.status,
        token_count=message.token_count,
        latency_ms=message.latency_ms,
        message_metadata=message.message_metadata,
        created_at=message.created_at,
        updated_at=message.updated_at,
        citations=[citation_to_response(citation) for citation in (citations or [])],
    )


async def create_document_message(
    *,
    session: AsyncSession,
    current_user: User,
    conversation_id: uuid.UUID,
    request: MessageCreate,
) -> DocumentMessageExchange:
    conversation = await get_conversation(
        session=session,
        current_user=current_user,
        conversation_id=conversation_id,
    )

    if conversation.mode != "document":
        raise UnsupportedConversationModeError(
            "This endpoint currently supports document conversations only."
        )

    if conversation.knowledge_base_id is None:
        raise UnsupportedConversationModeError(
            "The document conversation has no knowledge base."
        )

    normalized_question = request.content.strip()
    started_at = perf_counter()

    matches = await retrieve_relevant_chunks(
        session=session,
        current_user=current_user,
        knowledge_base_id=(conversation.knowledge_base_id),
        query=normalized_question,
        top_k=request.top_k,
        minimum_similarity=(request.minimum_similarity),
    )

    assistant_content = build_grounded_document_response(
        question=normalized_question,
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
            "mode": "document",
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
            "mode": "document",
            "retrieved_chunk_count": len(matches),
            "grounded": bool(matches),
        },
    )

    citation_records = [
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
    ]

    (
        saved_user_message,
        saved_assistant_message,
        saved_citations,
    ) = await create_message_exchange(
        session=session,
        user_message=user_message,
        assistant_message=assistant_message,
        citations=citation_records,
    )

    return DocumentMessageExchange(
        user_message=message_to_response(
            message=saved_user_message,
        ),
        assistant_message=message_to_response(
            message=saved_assistant_message,
            citations=saved_citations,
        ),
    )


async def get_conversation_messages(
    *,
    session: AsyncSession,
    current_user: User,
    conversation_id: uuid.UUID,
    offset: int,
    limit: int,
) -> tuple[list[MessageResponse], int]:
    conversation = await get_conversation(
        session=session,
        current_user=current_user,
        conversation_id=conversation_id,
    )

    messages, total = await list_message_records(
        session=session,
        tenant_id=current_user.tenant_id,
        conversation_id=conversation.id,
        offset=offset,
        limit=limit,
    )

    message_ids = [message.id for message in messages]

    citations_by_message = await list_message_citations(
        session=session,
        tenant_id=current_user.tenant_id,
        message_ids=message_ids,
    )

    items = [
        message_to_response(
            message=message,
            citations=citations_by_message.get(
                message.id,
                [],
            ),
        )
        for message in messages
    ]

    return items, total
