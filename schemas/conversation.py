import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConversationMode(StrEnum):
    DATABASE = "database"
    DOCUMENT = "document"
    HYBRID = "hybrid"


class ConversationCreate(BaseModel):
    title: str = Field(
        min_length=2,
        max_length=300,
        examples=["Company policy questions"],
    )
    mode: ConversationMode
    connection_id: uuid.UUID | None = None
    knowledge_base_id: uuid.UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_sources(self) -> "ConversationCreate":
        if self.mode == ConversationMode.DATABASE and self.connection_id is None:
            raise ValueError("Database conversations require a connection ID.")

        if self.mode == ConversationMode.DOCUMENT and self.knowledge_base_id is None:
            raise ValueError("Document conversations require a knowledge-base ID.")

        if self.mode == ConversationMode.HYBRID:
            if self.connection_id is None:
                raise ValueError("Hybrid conversations require a connection ID.")

            if self.knowledge_base_id is None:
                raise ValueError("Hybrid conversations require a knowledge-base ID.")

        return self


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    connection_id: uuid.UUID | None
    knowledge_base_id: uuid.UUID | None

    title: str
    mode: str
    status: str
    conversation_metadata: dict[str, Any]
    is_archived: bool

    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    items: list[ConversationResponse]
    total: int
