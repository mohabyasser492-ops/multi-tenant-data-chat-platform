import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from app.dependencies import CurrentUser, DatabaseSession
from schemas.permission import (
    TablePermissionCreate,
    TablePermissionListResponse,
    TablePermissionResponse,
)
from services.database.connection_service import (
    DatabaseConnectionNotFoundError,
    TenantAdministratorRequiredError,
)
from services.database.permission_service import (
    DuplicateTablePermissionError,
    PermissionResourceNotFoundError,
    create_permission,
    get_permissions,
)

router = APIRouter(
    prefix="/permissions",
    tags=["Permissions"],
)


@router.post(
    "",
    response_model=TablePermissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create table and column access rules",
)
async def create_permission_endpoint(
    request: TablePermissionCreate,
    session: DatabaseSession,
    current_user: CurrentUser,
) -> TablePermissionResponse:
    try:
        return await create_permission(
            session=session,
            current_user=current_user,
            request=request,
        )
    except TenantAdministratorRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant administrator access is required.",
        ) from exc
    except (
        DatabaseConnectionNotFoundError,
        PermissionResourceNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DuplicateTablePermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        await session.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The permission could not be created.",
        ) from exc


@router.get(
    "",
    response_model=TablePermissionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List permissions for the active tenant",
)
async def list_permissions_endpoint(
    session: DatabaseSession,
    current_user: CurrentUser,
    connection_id: Annotated[
        uuid.UUID | None,
        Query(),
    ] = None,
    table_id: Annotated[
        uuid.UUID | None,
        Query(),
    ] = None,
) -> TablePermissionListResponse:
    try:
        items, total = await get_permissions(
            session=session,
            current_user=current_user,
            connection_id=connection_id,
            table_id=table_id,
        )
    except DatabaseConnectionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database connection was not found.",
        ) from exc

    return TablePermissionListResponse(
        items=items,
        total=total,
    )
