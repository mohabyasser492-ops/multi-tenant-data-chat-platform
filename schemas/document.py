import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    knowledge_base_id: uuid.UUID
    uploaded_by: uuid.UUID | None

    original_filename: str
    content_type: str | None
    file_extension: str
    file_size_bytes: int
    checksum_sha256: str

    status: str
    processing_message: str | None
    page_count: int | None
    chunk_count: int
    document_metadata: dict[str, Any]

    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
