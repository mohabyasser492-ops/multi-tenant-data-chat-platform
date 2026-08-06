import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MessageCreate(BaseModel):
    content: str = Field(
        min_length=2,
        max_length=10_000,
        examples=["What is this document about?"],
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


class MessageCitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    citation_type: str
    document_id: uuid.UUID | None
    document_chunk_id: uuid.UUID | None
    query_execution_id: uuid.UUID | None
    source_name: str
    excerpt: str | None
    page_number: int | None
    section_title: str | None
    similarity_score: float | None
    citation_metadata: dict[str, Any]


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    conversation_id: uuid.UUID
    user_id: uuid.UUID | None
    role: str
    content: str
    status: str
    token_count: int | None
    latency_ms: int | None
    message_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    citations: list[MessageCitationResponse] = Field(
        default_factory=list,
    )


class ConversationMessageExchangeResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse


class MessageListResponse(BaseModel):
    items: list[MessageResponse]
    total: int
