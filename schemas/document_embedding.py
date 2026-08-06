import uuid

from pydantic import BaseModel


class DocumentEmbeddingResponse(BaseModel):
    document_id: uuid.UUID
    status: str
    chunk_count: int
    embedded_chunk_count: int
    embedding_model: str
    embedding_dimension: int
    message: str
