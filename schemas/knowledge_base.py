import uuid
from datetime import datetime
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=200,
        examples=["Company Documents"],
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
    )
    chunk_size: int = Field(
        default=800,
        ge=100,
        le=5000,
    )
    chunk_overlap: int = Field(
        default=120,
        ge=0,
        le=1000,
    )
    settings: dict[str, Any] = Field(
        default_factory=dict,
    )

    @model_validator(mode="after")
    def validate_chunk_configuration(
        self,
    ) -> "KnowledgeBaseCreate":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("Chunk overlap must be smaller than chunk size.")

        return self


class KnowledgeBaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    created_by: uuid.UUID | None
    name: str
    description: str | None
    embedding_model: str
    embedding_dimension: int
    chunk_size: int
    chunk_overlap: int
    settings_data: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseListResponse(BaseModel):
    items: list[KnowledgeBaseResponse]
    total: int
