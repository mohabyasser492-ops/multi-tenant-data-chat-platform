from sqlalchemy.ext.asyncio import AsyncSession

from core.encryption import encrypt_secret
from models.database_connection import DatabaseConnection
from models.user import User
from repositories.connections import (
    create_connection,
    get_connection_by_name,
    list_connections,
)
from schemas.database_connection import DatabaseConnectionCreate


class DuplicateConnectionNameError(ValueError):
    """Raised when a tenant already uses a connection name."""


class TenantAdministratorRequiredError(PermissionError):
    """Raised when a non-administrator performs an admin operation."""


def require_tenant_administrator(user: User) -> None:
    if not user.is_tenant_admin:
        raise TenantAdministratorRequiredError(
            "Tenant administrator access is required."
        )


async def create_database_connection(
    *,
    session: AsyncSession,
    current_user: User,
    request: DatabaseConnectionCreate,
) -> DatabaseConnection:
    require_tenant_administrator(current_user)

    normalized_name = request.name.strip()

    existing_connection = await get_connection_by_name(
        session=session,
        tenant_id=current_user.tenant_id,
        name=normalized_name,
    )

    if existing_connection is not None:
        raise DuplicateConnectionNameError(
            "A database connection with this name already exists."
        )

    encrypted_password = None
    encrypted_connection_string = None

    if request.password is not None:
        encrypted_password = encrypt_secret(request.password.get_secret_value())

    if request.connection_string is not None:
        encrypted_connection_string = encrypt_secret(
            request.connection_string.get_secret_value()
        )

    connection = DatabaseConnection(
        tenant_id=current_user.tenant_id,
        created_by=current_user.id,
        name=normalized_name,
        database_type=request.database_type.value,
        host=request.host,
        port=request.port,
        database_name=request.database_name,
        username=request.username,
        encrypted_password=encrypted_password,
        encrypted_connection_string=encrypted_connection_string,
        ssl_enabled=request.ssl_enabled,
        ssl_settings=request.ssl_settings,
        connection_options=request.connection_options,
        status="pending",
        schema_sync_status="pending",
        is_active=True,
    )

    return await create_connection(
        session=session,
        connection=connection,
    )


async def list_database_connections(
    *,
    session: AsyncSession,
    current_user: User,
    offset: int,
    limit: int,
) -> tuple[list[DatabaseConnection], int]:
    return await list_connections(
        session=session,
        tenant_id=current_user.tenant_id,
        offset=offset,
        limit=limit,
    )
