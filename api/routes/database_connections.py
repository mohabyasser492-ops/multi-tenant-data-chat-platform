import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError

from app.dependencies import CurrentUser, DatabaseSession
from schemas.database_connection import (
    DatabaseConnectionCreate,
    DatabaseConnectionListResponse,
    DatabaseConnectionResponse,
    DatabaseConnectionTestResponse,
    DatabaseConnectionUpdate,
)
from schemas.database_schema import SchemaSyncResponse
from services.database.connection_service import (
    DatabaseConnectionNotFoundError,
    DuplicateConnectionNameError,
    TenantAdministratorRequiredError,
    create_database_connection,
    get_database_connection,
    list_database_connections,
    remove_database_connection,
    test_stored_database_connection,
    update_database_connection,
)
from services.database.connection_tester import (
    UnsupportedDatabaseTypeError,
)
from services.database.schema_discovery import SchemaDiscoveryError
from services.database.schema_sync_service import (
    synchronize_database_schema,
)

router = APIRouter(
    prefix="/database-connections",
    tags=["Database Connections"],
)


@router.post(
    "",
    response_model=DatabaseConnectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a runtime database connection",
)
async def create_connection_endpoint(
    request: DatabaseConnectionCreate,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> DatabaseConnectionResponse:
    try:
        connection = await create_database_connection(
            session=session,
            current_user=current_user,
            request=request,
        )
    except TenantAdministratorRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant administrator access is required.",
        ) from exc
    except DuplicateConnectionNameError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        await session.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The database connection could not be created.",
        ) from exc

    return DatabaseConnectionResponse.model_validate(connection)


@router.get(
    "",
    response_model=DatabaseConnectionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List database connections for the active tenant",
)
async def list_connections_endpoint(
    session: DatabaseSession,
    current_user: CurrentUser,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DatabaseConnectionListResponse:
    connections, total = await list_database_connections(
        session=session,
        current_user=current_user,
        offset=offset,
        limit=limit,
    )

    return DatabaseConnectionListResponse(
        items=[
            DatabaseConnectionResponse.model_validate(connection)
            for connection in connections
        ],
        total=total,
    )


@router.post(
    "/{connection_id}/test",
    response_model=DatabaseConnectionTestResponse,
    status_code=status.HTTP_200_OK,
    summary="Test a stored database connection",
)
async def test_connection_endpoint(
    connection_id: uuid.UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> DatabaseConnectionTestResponse:
    try:
        connection, result = await test_stored_database_connection(
            session=session,
            current_user=current_user,
            connection_id=connection_id,
        )
    except DatabaseConnectionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database connection was not found.",
        ) from exc
    except TenantAdministratorRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant administrator access is required.",
        ) from exc
    except UnsupportedDatabaseTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=("Connection testing is not available for this database type."),
        ) from exc

    if connection.last_tested_at is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Connection test timestamp was not recorded.",
        )

    return DatabaseConnectionTestResponse(
        connection_id=connection.id,
        success=result.success,
        status=connection.status,
        message=result.message,
        tested_at=connection.last_tested_at,
    )


@router.post(
    "/{connection_id}/sync-schema",
    response_model=SchemaSyncResponse,
    status_code=status.HTTP_200_OK,
    summary="Discover and cache database schema metadata",
)
async def sync_schema_endpoint(
    connection_id: uuid.UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> SchemaSyncResponse:
    try:
        result = await synchronize_database_schema(
            session=session,
            current_user=current_user,
            connection_id=connection_id,
        )
    except DatabaseConnectionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database connection was not found.",
        ) from exc
    except TenantAdministratorRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant administrator access is required.",
        ) from exc
    except SchemaDiscoveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Database schema discovery failed.",
        ) from exc

    return SchemaSyncResponse(
        connection_id=result.connection.id,
        status=result.connection.schema_sync_status,
        schema_count=result.schema_count,
        table_count=result.table_count,
        column_count=result.column_count,
        synchronized_at=result.synchronized_at,
    )


@router.get(
    "/{connection_id}",
    response_model=DatabaseConnectionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a database connection",
)
async def get_connection_endpoint(
    connection_id: uuid.UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> DatabaseConnectionResponse:
    try:
        connection = await get_database_connection(
            session=session,
            current_user=current_user,
            connection_id=connection_id,
        )
    except DatabaseConnectionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database connection was not found.",
        ) from exc

    return DatabaseConnectionResponse.model_validate(connection)


@router.put(
    "/{connection_id}",
    response_model=DatabaseConnectionResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a database connection",
)
async def update_connection_endpoint(
    connection_id: uuid.UUID,
    request: DatabaseConnectionUpdate,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> DatabaseConnectionResponse:
    try:
        connection = await update_database_connection(
            session=session,
            current_user=current_user,
            connection_id=connection_id,
            request=request,
        )
    except DatabaseConnectionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database connection was not found.",
        ) from exc
    except TenantAdministratorRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant administrator access is required.",
        ) from exc
    except DuplicateConnectionNameError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        await session.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The database connection could not be updated.",
        ) from exc

    return DatabaseConnectionResponse.model_validate(connection)


@router.delete(
    "/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a database connection",
)
async def delete_connection_endpoint(
    connection_id: uuid.UUID,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> Response:
    try:
        await remove_database_connection(
            session=session,
            current_user=current_user,
            connection_id=connection_id,
        )
    except DatabaseConnectionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database connection was not found.",
        ) from exc
    except TenantAdministratorRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant administrator access is required.",
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
