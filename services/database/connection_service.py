import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from core.encryption import encrypt_secret
from models.database_connection import DatabaseConnection
from models.user import User
from repositories.connections import (
    create_connection,
    delete_connection,
    get_connection_by_id,
    get_connection_by_name,
    list_connections,
    save_connection,
)
from schemas.database_connection import (
    DatabaseConnectionCreate,
    DatabaseConnectionUpdate,
)
from services.database.connection_tester import (
    ConnectionTestResult,
    UnsupportedDatabaseTypeError,
    test_database_connection,
)


class DuplicateConnectionNameError(ValueError):
    """Raised when a tenant already uses a connection name."""


class DatabaseConnectionNotFoundError(LookupError):
    """Raised when a connection is unavailable to the active tenant."""


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

    encrypted_password: str | None = None
    encrypted_connection_string: str | None = None

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


async def get_database_connection(
    *,
    session: AsyncSession,
    current_user: User,
    connection_id: uuid.UUID,
) -> DatabaseConnection:
    connection = await get_connection_by_id(
        session=session,
        tenant_id=current_user.tenant_id,
        connection_id=connection_id,
    )

    if connection is None:
        raise DatabaseConnectionNotFoundError("Database connection was not found.")

    return connection


async def update_database_connection(
    *,
    session: AsyncSession,
    current_user: User,
    connection_id: uuid.UUID,
    request: DatabaseConnectionUpdate,
) -> DatabaseConnection:
    require_tenant_administrator(current_user)

    connection = await get_database_connection(
        session=session,
        current_user=current_user,
        connection_id=connection_id,
    )

    update_data = request.model_dump(
        exclude_unset=True,
        exclude={
            "password",
            "connection_string",
        },
    )

    if "name" in update_data:
        normalized_name = update_data["name"].strip()

        existing_connection = await get_connection_by_name(
            session=session,
            tenant_id=current_user.tenant_id,
            name=normalized_name,
        )

        if existing_connection is not None and existing_connection.id != connection.id:
            raise DuplicateConnectionNameError(
                "A database connection with this name already exists."
            )

        update_data["name"] = normalized_name

    for field_name, value in update_data.items():
        setattr(connection, field_name, value)

    if request.password is not None:
        connection.encrypted_password = encrypt_secret(
            request.password.get_secret_value()
        )

    if request.connection_string is not None:
        connection.encrypted_connection_string = encrypt_secret(
            request.connection_string.get_secret_value()
        )

    connection.status = "pending"
    connection.last_tested_at = None
    connection.last_test_message = None
    connection.schema_sync_status = "pending"
    connection.last_schema_sync_at = None

    return await save_connection(
        session=session,
        connection=connection,
    )


async def remove_database_connection(
    *,
    session: AsyncSession,
    current_user: User,
    connection_id: uuid.UUID,
) -> None:
    require_tenant_administrator(current_user)

    connection = await get_database_connection(
        session=session,
        current_user=current_user,
        connection_id=connection_id,
    )

    await delete_connection(
        session=session,
        connection=connection,
    )


async def test_stored_database_connection(
    *,
    session: AsyncSession,
    current_user: User,
    connection_id: uuid.UUID,
) -> tuple[DatabaseConnection, ConnectionTestResult]:
    require_tenant_administrator(current_user)

    connection = await get_database_connection(
        session=session,
        current_user=current_user,
        connection_id=connection_id,
    )

    tested_at = datetime.now(UTC)

    try:
        result = await test_database_connection(
            connection,
            timeout_seconds=settings.sql_timeout_seconds,
        )
    except UnsupportedDatabaseTypeError:
        connection.status = "failed"
        connection.last_tested_at = tested_at
        connection.last_test_message = (
            "Connection testing is not available for this database type."
        )

        await save_connection(
            session=session,
            connection=connection,
        )

        raise

    connection.status = "connected" if result.success else "failed"
    connection.last_tested_at = tested_at
    connection.last_test_message = result.message

    saved_connection = await save_connection(
        session=session,
        connection=connection,
    )

    return saved_connection, result
