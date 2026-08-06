from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from app.dependencies import CurrentUser, DatabaseSession
from schemas.database_connection import (
    DatabaseConnectionCreate,
    DatabaseConnectionListResponse,
    DatabaseConnectionResponse,
)
from services.database.connection_service import (
    DuplicateConnectionNameError,
    TenantAdministratorRequiredError,
    create_database_connection,
    list_database_connections,
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
async def create_connection(
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
async def get_connections(
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
