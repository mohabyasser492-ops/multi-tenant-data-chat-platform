import uuid

from pydantic import BaseModel, Field


class KnowledgeBaseSearchRequest(BaseModel):
    query: str = Field(
        min_length=2,
        max_length=5000,
        examples=["What does the company policy say?"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
    )
    minimum_similarity: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )


class DocumentCitationResponse(BaseModel):
    document_id: uuid.UUID
    document_name: str
    chunk_id: uuid.UUID
    chunk_index: int
    page_number: int | None
    section_title: str | None
    similarity_score: float
    content: str


class KnowledgeBaseSearchResponse(BaseModel):
    knowledge_base_id: uuid.UUID
    query: str
    matches: list[DocumentCitationResponse]
    total: int
