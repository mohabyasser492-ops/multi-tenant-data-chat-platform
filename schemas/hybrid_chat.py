from pydantic import BaseModel, Field


class HybridMessageCreate(BaseModel):
    content: str = Field(
        min_length=2,
        max_length=10_000,
        examples=["Compare the permitted database results with the documents."],
    )
    proposed_sql: str = Field(
        min_length=1,
        max_length=50_000,
        examples=["SELECT email FROM public.users"],
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
