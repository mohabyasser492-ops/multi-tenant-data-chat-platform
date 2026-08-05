import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from schemas.database_connection import (
    DatabaseConnectionCreate,
    DatabaseConnectionResponse,
    DatabaseType,
)


def test_create_connection_with_individual_fields() -> None:
    request = DatabaseConnectionCreate(
        name="Sales PostgreSQL",
        database_type=DatabaseType.POSTGRESQL,
        host="localhost",
        port=5432,
        database_name="sales",
        username="readonly_user",
        password="DatabasePassword123!",
    )

    assert request.database_type == DatabaseType.POSTGRESQL
    assert request.password is not None
    assert request.password.get_secret_value() == "DatabasePassword123!"


def test_create_connection_with_connection_string() -> None:
    request = DatabaseConnectionCreate(
        name="Sales PostgreSQL",
        database_type=DatabaseType.POSTGRESQL,
        connection_string=("postgresql://readonly_user:secret@localhost:5432/sales"),
    )

    assert request.connection_string is not None


def test_create_connection_requires_credentials() -> None:
    with pytest.raises(
        ValidationError,
        match="Provide either a connection string",
    ):
        DatabaseConnectionCreate(
            name="Missing Credentials",
            database_type=DatabaseType.POSTGRESQL,
        )


def test_create_connection_rejects_invalid_port() -> None:
    with pytest.raises(ValidationError):
        DatabaseConnectionCreate(
            name="Invalid Port",
            database_type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=70000,
            database_name="sales",
            username="readonly_user",
            password="DatabasePassword123!",
        )


def test_response_does_not_expose_credentials() -> None:
    now = datetime.now(UTC)

    response = DatabaseConnectionResponse.model_validate(
        {
            "id": uuid.uuid4(),
            "tenant_id": uuid.uuid4(),
            "created_by": uuid.uuid4(),
            "name": "Sales PostgreSQL",
            "database_type": "postgresql",
            "host": "localhost",
            "port": 5432,
            "database_name": "sales",
            "username": "readonly_user",
            "encrypted_password": "encrypted-secret",
            "encrypted_connection_string": "encrypted-url",
            "ssl_enabled": False,
            "ssl_settings": {},
            "connection_options": {},
            "status": "pending",
            "last_tested_at": None,
            "last_test_message": None,
            "schema_sync_status": "pending",
            "last_schema_sync_at": None,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
    )

    response_data = response.model_dump()

    assert "password" not in response_data
    assert "connection_string" not in response_data
    assert "encrypted_password" not in response_data
    assert "encrypted_connection_string" not in response_data


def test_secret_values_are_masked_when_serialized() -> None:
    request = DatabaseConnectionCreate(
        name="Sales PostgreSQL",
        database_type=DatabaseType.POSTGRESQL,
        host="localhost",
        port=5432,
        database_name="sales",
        username="readonly_user",
        password="DatabasePassword123!",
    )

    serialized = request.model_dump(mode="json")

    assert serialized["password"] == "**********"
    assert "DatabasePassword123!" not in str(serialized)
