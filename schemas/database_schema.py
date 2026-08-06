import uuid
from datetime import datetime

from pydantic import BaseModel


class SchemaSyncResponse(BaseModel):
    connection_id: uuid.UUID
    status: str
    schema_count: int
    table_count: int
    column_count: int
    synchronized_at: datetime