import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from repositories.documents import (
    search_document_chunks,
)
from services.document.embedding_service import (
    EmbeddingGenerationError,
    generate_embeddings,
)
from services.document.knowledge_base_service import (
    get_knowledge_base,
)


@dataclass(slots=True)
class RetrievedDocumentChunk:
    document_id: uuid.UUID
    document_name: str
    chunk_id: uuid.UUID
    chunk_index: int
    page_number: int | None
    section_title: str | None
    similarity_score: float
    content: str


class DocumentRetrievalError(RuntimeError):
    """Raised when semantic retrieval cannot be completed safely."""


def cosine_distance_to_similarity(
    distance: float,
) -> float:
    similarity = 1.0 - distance

    return max(
        0.0,
        min(1.0, similarity),
    )


async def retrieve_relevant_chunks(
    *,
    session: AsyncSession,
    current_user: User,
    knowledge_base_id: uuid.UUID,
    query: str,
    top_k: int,
    minimum_similarity: float,
) -> list[RetrievedDocumentChunk]:
    knowledge_base = await get_knowledge_base(
        session=session,
        current_user=current_user,
        knowledge_base_id=knowledge_base_id,
    )

    if not knowledge_base.is_active:
        raise DocumentRetrievalError("The selected knowledge base is disabled.")

    normalized_query = query.strip()

    if not normalized_query:
        raise DocumentRetrievalError("The search query cannot be empty.")

    try:
        embeddings = await generate_embeddings(
            texts=[normalized_query],
            model_name=knowledge_base.embedding_model,
            expected_dimension=(knowledge_base.embedding_dimension),
        )
    except EmbeddingGenerationError as exc:
        raise DocumentRetrievalError("The search query could not be embedded.") from exc

    if not embeddings:
        raise DocumentRetrievalError("The search query produced no embedding.")

    search_rows = await search_document_chunks(
        session=session,
        tenant_id=current_user.tenant_id,
        knowledge_base_id=knowledge_base_id,
        query_embedding=embeddings[0],
        top_k=top_k,
    )

    matches: list[RetrievedDocumentChunk] = []

    for chunk, document, distance in search_rows:
        similarity_score = cosine_distance_to_similarity(distance)

        if similarity_score < minimum_similarity:
            continue

        matches.append(
            RetrievedDocumentChunk(
                document_id=document.id,
                document_name=(document.original_filename),
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                similarity_score=round(
                    similarity_score,
                    6,
                ),
                content=chunk.content,
            )
        )

    return matches
