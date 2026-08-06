import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.exc import IntegrityError

from app.dependencies import CurrentUser, DatabaseSession
from schemas.document import (
    DocumentListResponse,
    DocumentResponse,
)
from schemas.document_processing import (
    DocumentProcessingResponse,
)
from services.database.connection_service import (
    TenantAdministratorRequiredError,
)
from services.document.document_processor import (
    DocumentNotFoundError,
    DocumentProcessingError,
    process_document,
)
from services.document.document_service import (
    DuplicateDocumentError,
    InvalidDocumentError,
    list_documents,
    upload_document,
)
from services.document.knowledge_base_service import (
    KnowledgeBaseNotFoundError,
)
from services.storage.minio_service import (
    ObjectStorageError,
)

router = APIRouter(
    prefix="/knowledge-bases",
    tags=["Documents"],
)


@router.post(
    "/{knowledge_base_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document to a knowledge base",
)
async def upload_document_endpoint(
    knowledge_base_id: uuid.UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
    file: Annotated[UploadFile, File()],
) -> DocumentResponse:
    try:
        document = await upload_document(
            session=session,
            current_user=current_user,
            knowledge_base_id=knowledge_base_id,
            upload=file,
        )
    except TenantAdministratorRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant administrator access is required.",
        ) from exc
    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base was not found.",
        ) from exc
    except InvalidDocumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except DuplicateDocumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ObjectStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The document could not be stored.",
        ) from exc
    except IntegrityError as exc:
        await session.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The document record could not be created.",
        ) from exc
    finally:
        await file.close()

    return DocumentResponse.model_validate(document)


@router.get(
    "/{knowledge_base_id}/documents",
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List documents in a knowledge base",
)
async def list_documents_endpoint(
    knowledge_base_id: uuid.UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DocumentListResponse:
    try:
        documents, total = await list_documents(
            session=session,
            current_user=current_user,
            knowledge_base_id=knowledge_base_id,
            offset=offset,
            limit=limit,
        )
    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base was not found.",
        ) from exc

    return DocumentListResponse(
        items=[DocumentResponse.model_validate(document) for document in documents],
        total=total,
    )


@router.post(
    "/{knowledge_base_id}/documents/{document_id}/process",
    response_model=DocumentProcessingResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract and chunk an uploaded document",
)
async def process_document_endpoint(
    knowledge_base_id: uuid.UUID,
    document_id: uuid.UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> DocumentProcessingResponse:
    try:
        document = await process_document(
            session=session,
            current_user=current_user,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
        )
    except TenantAdministratorRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant administrator access is required.",
        ) from exc
    except KnowledgeBaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base was not found.",
        ) from exc
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document was not found.",
        ) from exc
    except DocumentProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The document could not be processed.",
        ) from exc

    return DocumentProcessingResponse(
        document_id=document.id,
        status=document.status,
        page_count=document.page_count,
        chunk_count=document.chunk_count,
        message=(document.processing_message or "Document processing completed."),
    )
