import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import CurrentUser, DatabaseSession
from schemas.database_schema import (
    DatabaseSchemaListResponse,
    DatabaseSchemaResponse,
    DatabaseTableListResponse,
)
from services.database.connection_service import (
    DatabaseConnectionNotFoundError,
)
from services.database.metadata_query_service import (
    get_cached_schemas,
    get_cached_tables,
)

router = APIRouter(
    prefix="/database-connections",
    tags=["Database Schema"],
)


@router.get(
    "/{connection_id}/schemas",
    response_model=DatabaseSchemaListResponse,
    status_code=status.HTTP_200_OK,
    summary="List cached schemas for a database connection",
)
async def list_schemas_endpoint(
    connection_id: uuid.UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> DatabaseSchemaListResponse:
    try:
        schemas, total = await get_cached_schemas(
            session=session,
            current_user=current_user,
            connection_id=connection_id,
        )
    except DatabaseConnectionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database connection was not found.",
        ) from exc

    return DatabaseSchemaListResponse(
        items=[DatabaseSchemaResponse.model_validate(schema) for schema in schemas],
        total=total,
    )


@router.get(
    "/{connection_id}/tables",
    response_model=DatabaseTableListResponse,
    status_code=status.HTTP_200_OK,
    summary="List cached tables and columns",
)
async def list_tables_endpoint(
    connection_id: uuid.UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
    schema_name: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=255,
            description="Optionally filter tables by schema name.",
        ),
    ] = None,
) -> DatabaseTableListResponse:
    try:
        tables, total = await get_cached_tables(
            session=session,
            current_user=current_user,
            connection_id=connection_id,
            schema_name=schema_name,
        )
    except DatabaseConnectionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database connection was not found.",
        ) from exc

    return DatabaseTableListResponse(
        items=tables,
        total=total,
    )
