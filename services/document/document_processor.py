import uuid

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from models.knowledge_base import (
    Document,
    DocumentChunk,
)
from models.user import User
from repositories.documents import (
    get_document_by_id,
    replace_document_chunks,
    save_document_record,
)
from services.database.connection_service import (
    require_tenant_administrator,
)
from services.document.knowledge_base_service import (
    get_knowledge_base,
)
from services.document.text_chunker import (
    TextChunkingError,
    chunk_extracted_document,
)
from services.document.text_extractor import (
    DocumentExtractionError,
    extract_document_text,
)
from services.storage.minio_service import (
    ObjectStorageError,
    minio_storage,
)


class DocumentNotFoundError(LookupError):
    """Raised when a document is unavailable to the active tenant."""


class DocumentProcessingError(RuntimeError):
    """Raised when document extraction or chunking fails safely."""


async def get_document_for_processing(
    *,
    session: AsyncSession,
    current_user: User,
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
) -> Document:
    document = await get_document_by_id(
        session=session,
        tenant_id=current_user.tenant_id,
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
    )

    if document is None:
        raise DocumentNotFoundError("Document was not found.")

    return document


async def mark_document_failed(
    *,
    session: AsyncSession,
    document: Document,
    message: str,
) -> None:
    document.status = "failed"
    document.processing_message = message
    document.page_count = None
    document.chunk_count = 0

    try:
        await save_document_record(
            session=session,
            document=document,
        )
    except SQLAlchemyError:
        await session.rollback()


async def process_document(
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

    document.status = "processing"
    document.processing_message = "Extracting and chunking document text."

    await save_document_record(
        session=session,
        document=document,
    )

    try:
        content = await minio_storage.download_bytes(object_key=document.storage_key)

        extracted_document = extract_document_text(
            content=content,
            file_extension=document.file_extension,
        )

        text_chunks = chunk_extracted_document(
            document=extracted_document,
            chunk_size=knowledge_base.chunk_size,
            chunk_overlap=knowledge_base.chunk_overlap,
        )

        chunk_records = [
            DocumentChunk(
                tenant_id=current_user.tenant_id,
                knowledge_base_id=knowledge_base.id,
                document_id=document.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                token_count=chunk.token_count,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                chunk_metadata=chunk.metadata,
                embedding=None,
            )
            for chunk in text_chunks
        ]

        await replace_document_chunks(
            session=session,
            document=document,
            chunks=chunk_records,
        )

    except (
        ObjectStorageError,
        DocumentExtractionError,
        TextChunkingError,
    ) as exc:
        await mark_document_failed(
            session=session,
            document=document,
            message=str(exc),
        )

        raise DocumentProcessingError("The document could not be processed.") from exc
    except SQLAlchemyError as exc:
        await session.rollback()

        await mark_document_failed(
            session=session,
            document=document,
            message=("The document chunks could not be stored."),
        )

        raise DocumentProcessingError("The document could not be processed.") from exc

    document.status = "chunked"
    document.processing_message = (
        "Document text was extracted and chunked successfully."
    )
    document.page_count = extracted_document.page_count
    document.chunk_count = len(chunk_records)

    return await save_document_record(
        session=session,
        document=document,
    )
