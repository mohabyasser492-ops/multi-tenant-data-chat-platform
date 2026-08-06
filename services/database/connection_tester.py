import asyncio
from dataclasses import dataclass

import asyncpg
from sqlalchemy.engine import make_url

from core.encryption import decrypt_secret
from models.database_connection import DatabaseConnection


@dataclass(slots=True)
class ConnectionTestResult:
    success: bool
    message: str


class UnsupportedDatabaseTypeError(ValueError):
    """Raised when testing is unavailable for a database type."""


def build_postgresql_parameters(
    connection: DatabaseConnection,
) -> dict[str, str | int]:
    if connection.encrypted_connection_string:
        connection_string = decrypt_secret(connection.encrypted_connection_string)
        url = make_url(connection_string)

        if not url.host or not url.database or not url.username:
            raise ValueError("The stored PostgreSQL connection string is incomplete.")

        if not url.password:
            raise ValueError("The stored PostgreSQL connection string has no password.")

        return {
            "host": url.host,
            "port": url.port or 5432,
            "database": url.database,
            "user": url.username,
            "password": url.password,
        }

    if not all(
        [
            connection.host,
            connection.port,
            connection.database_name,
            connection.username,
            connection.encrypted_password,
        ]
    ):
        raise ValueError("The stored database connection details are incomplete.")

    return {
        "host": connection.host,
        "port": connection.port,
        "database": connection.database_name,
        "user": connection.username,
        "password": decrypt_secret(connection.encrypted_password),
    }


async def test_postgresql_connection(
    connection: DatabaseConnection,
    *,
    timeout_seconds: int = 10,
) -> ConnectionTestResult:
    parameters = build_postgresql_parameters(connection)
    source_connection: asyncpg.Connection | None = None

    try:
        source_connection = await asyncio.wait_for(
            asyncpg.connect(
                **parameters,
                ssl="require" if connection.ssl_enabled else None,
                command_timeout=timeout_seconds,
                server_settings={
                    "application_name": "multi_tenant_data_chat",
                },
            ),
            timeout=timeout_seconds,
        )

        await asyncio.wait_for(
            source_connection.fetchval("SELECT 1"),
            timeout=timeout_seconds,
        )

        return ConnectionTestResult(
            success=True,
            message="Database connection tested successfully.",
        )

    except TimeoutError:
        return ConnectionTestResult(
            success=False,
            message="Database connection test timed out.",
        )
    except (asyncpg.PostgresError, OSError, ValueError):
        return ConnectionTestResult(
            success=False,
            message="Database connection test failed.",
        )
    finally:
        if source_connection is not None:
            await source_connection.close()


async def test_database_connection(
    connection: DatabaseConnection,
    *,
    timeout_seconds: int = 10,
) -> ConnectionTestResult:
    if connection.database_type != "postgresql":
        raise UnsupportedDatabaseTypeError(
            "Connection testing is currently implemented for PostgreSQL."
        )

    return await test_postgresql_connection(
        connection,
        timeout_seconds=timeout_seconds,
    )
