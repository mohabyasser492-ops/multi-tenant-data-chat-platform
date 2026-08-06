import hashlib
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from models.knowledge_base import Document
from models.user import User
from repositories.documents import (
    create_document_record,
    get_document_by_checksum,
    list_document_records,
)
from services.database.connection_service import (
    require_tenant_administrator,
)
from services.document.knowledge_base_service import (
    get_knowledge_base,
)
from services.storage.minio_service import (
    ObjectStorageError,
    build_document_storage_key,
    minio_storage,
)


class InvalidDocumentError(ValueError):
    """Raised when an uploaded document fails validation."""


class DuplicateDocumentError(ValueError):
    """Raised when the same file already exists in a knowledge base."""


def normalize_extension(filename: str) -> str:
    extension = Path(filename).suffix.lower().lstrip(".")

    if not extension:
        raise InvalidDocumentError("The uploaded file does not have an extension.")

    return extension


def validate_file_extension(extension: str) -> None:
    allowed_extensions = {
        item.lower().lstrip(".") for item in settings.allowed_extensions
    }

    if extension not in allowed_extensions:
        raise InvalidDocumentError("The uploaded file type is not supported.")


def validate_file_size(content: bytes) -> None:
    if not content:
        raise InvalidDocumentError("An empty file cannot be uploaded.")

    maximum_size_bytes = settings.max_upload_size_mb * 1024 * 1024

    if len(content) > maximum_size_bytes:
        raise InvalidDocumentError("The uploaded file exceeds the maximum size.")


def calculate_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


async def upload_document(
    *,
    session: AsyncSession,
    current_user: User,
    knowledge_base_id: uuid.UUID,
    upload: UploadFile,
) -> Document:
    require_tenant_administrator(current_user)

    knowledge_base = await get_knowledge_base(
        session=session,
        current_user=current_user,
        knowledge_base_id=knowledge_base_id,
    )

    if not knowledge_base.is_active:
        raise InvalidDocumentError("The selected knowledge base is disabled.")

    if not upload.filename:
        raise InvalidDocumentError("The uploaded filename is required.")

    extension = normalize_extension(upload.filename)
    validate_file_extension(extension)

    content = await upload.read()
    validate_file_size(content)

    checksum_sha256 = calculate_sha256(content)

    existing_document = await get_document_by_checksum(
        session=session,
        tenant_id=current_user.tenant_id,
        knowledge_base_id=knowledge_base_id,
        checksum_sha256=checksum_sha256,
    )

    if existing_document is not None:
        raise DuplicateDocumentError(
            "This document already exists in the knowledge base."
        )

    document_id = uuid.uuid4()

    storage_key = build_document_storage_key(
        tenant_id=current_user.tenant_id,
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
        filename=upload.filename,
    )

    content_type = upload.content_type or "application/octet-stream"

    await minio_storage.upload_bytes(
        object_key=storage_key,
        content=content,
        content_type=content_type,
    )

    document = Document(
        id=document_id,
        tenant_id=current_user.tenant_id,
        knowledge_base_id=knowledge_base_id,
        uploaded_by=current_user.id,
        original_filename=upload.filename,
        storage_key=storage_key,
        content_type=content_type,
        file_extension=extension,
        file_size_bytes=len(content),
        checksum_sha256=checksum_sha256,
        status="pending",
        processing_message=("The document is waiting to be processed."),
        page_count=None,
        chunk_count=0,
        document_metadata={},
    )

    try:
        return await create_document_record(
            session=session,
            document=document,
        )
    except SQLAlchemyError:
        await session.rollback()

        try:
            await minio_storage.delete_object(object_key=storage_key)
        except ObjectStorageError:
            pass

        raise


async def list_documents(
    *,
    session: AsyncSession,
    current_user: User,
    knowledge_base_id: uuid.UUID,
    offset: int,
    limit: int,
) -> tuple[list[Document], int]:
    await get_knowledge_base(
        session=session,
        current_user=current_user,
        knowledge_base_id=knowledge_base_id,
    )

    return await list_document_records(
        session=session,
        tenant_id=current_user.tenant_id,
        knowledge_base_id=knowledge_base_id,
        offset=offset,
        limit=limit,
    )
