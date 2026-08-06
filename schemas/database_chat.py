from pydantic import BaseModel, Field


class DatabaseMessageCreate(BaseModel):
    content: str = Field(
        min_length=2,
        max_length=10_000,
        examples=["Show the permitted user emails."],
    )
    proposed_sql: str = Field(
        min_length=1,
        max_length=50_000,
        examples=["SELECT email FROM public.users"],
    )
