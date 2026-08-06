import uuid

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from models.knowledge_base import Document
from models.user import User
from repositories.documents import (
    list_document_chunks,
    save_document_embeddings,
    save_document_record,
)
from services.database.connection_service import (
    require_tenant_administrator,
)
from services.document.document_processor import (
    get_document_for_processing,
    mark_document_failed,
)
from services.document.embedding_service import (
    EmbeddingGenerationError,
    generate_embeddings,
)
from services.document.knowledge_base_service import (
    get_knowledge_base,
)


class DocumentEmbeddingError(RuntimeError):
    """Raised when a document cannot be embedded safely."""


async def embed_document_chunks(
    *,
    session: AsyncSession,
    current_user: User,
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
) -> Document:
    require_tenant_administrator(current_user)

    knowledge_base = await get_knowledge_base(
        session=session,
        current_user=current_user,
        knowledge_base_id=knowledge_base_id,
    )

    document = await get_document_for_processing(
        session=session,
        current_user=current_user,
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
    )

    if document.status not in {
        "chunked",
        "completed",
    }:
        raise DocumentEmbeddingError(
            "The document must be extracted and chunked "
            "before embeddings can be generated."
        )

    chunks = await list_document_chunks(
        session=session,
        tenant_id=current_user.tenant_id,
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
    )

    if not chunks:
        raise DocumentEmbeddingError("The document does not contain any stored chunks.")

    document.status = "embedding"
    document.processing_message = "Generating vector embeddings for document chunks."

    await save_document_record(
        session=session,
        document=document,
    )

    try:
        embeddings = await generate_embeddings(
            texts=[chunk.content for chunk in chunks],
            model_name=knowledge_base.embedding_model,
            expected_dimension=(knowledge_base.embedding_dimension),
        )

        for chunk, embedding in zip(
            chunks,
            embeddings,
            strict=True,
        ):
            chunk.embedding = embedding

        document.status = "completed"
        document.processing_message = "Document processing and embedding completed."
        document.chunk_count = len(chunks)

        return await save_document_embeddings(
            session=session,
            document=document,
            chunks=chunks,
        )

    except EmbeddingGenerationError as exc:
        await mark_document_failed(
            session=session,
            document=document,
            message=("Document embeddings could not be generated."),
        )

        raise DocumentEmbeddingError(
            "The document embeddings could not be generated."
        ) from exc

    except SQLAlchemyError as exc:
        await session.rollback()

        await mark_document_failed(
            session=session,
            document=document,
            message=("Document embeddings could not be stored."),
        )

        raise DocumentEmbeddingError(
            "The document embeddings could not be stored."
        ) from exc
