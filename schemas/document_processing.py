import uuid

from pydantic import BaseModel


class DocumentProcessingResponse(BaseModel):
    document_id: uuid.UUID
    status: str
    page_count: int | None
    chunk_count: int
    message: str
