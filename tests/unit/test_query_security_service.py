import uuid

import pytest

from core.permissions import (
    AllowedColumn,
    AllowedSchema,
    AllowedTable,
)
from services.database.query_security_service import (
    QuerySecurityError,
    prepare_validated_sql,
)

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


def build_allowed_schema(
    *,
    include_row_filter: bool = False,
) -> AllowedSchema:
    tenant_column = AllowedColumn(
        column_id="tenant-column-id",
        name="tenant_id",
        data_type="uuid",
        can_read=True,
        can_filter=True,
        can_aggregate=False,
        mask_type=None,
    )

    email_column = AllowedColumn(
        column_id="email-column-id",
        name="email",
        data_type="character varying",
        can_read=True,
        can_filter=True,
        can_aggregate=False,
        mask_type="email",
    )

    row_filters = []

    if include_row_filter:
        row_filters = [
            {
                "match": "all",
                "rules": [
                    {
                        "column_id": "tenant-column-id",
                        "operator": "eq",
                        "value_source": "tenant_id",
                    }
                ],
            }
        ]

    users_table = AllowedTable(
        table_id="users-table-id",
        schema_name="public",
        table_name="users",
        can_read=True,
        can_insert=False,
        can_update=False,
        can_delete=False,
        columns={
            "tenant_id": tenant_column,
            "email": email_column,
        },
        row_filters=row_filters,
    )

    return AllowedSchema(
        connection_id="connection-id",
        tables={
            "public.users": users_table,
        },
    )


def test_valid_query_passes_pipeline() -> None:
    result = prepare_validated_sql(
        sql="SELECT email FROM public.users",
        allowed_schema=build_allowed_schema(),
        tenant_id=TENANT_ID,
        user_id=USER_ID,
        maximum_rows=100,
    )

    assert "SELECT email FROM public.users" in result.sql
    assert "LIMIT 100" in result.sql
    assert result.applied_limit == 100
    assert result.row_filters_applied is False
    assert result.referenced_tables == ["public.users"]
    assert result.referenced_columns == ["public.users.email"]


def test_mandatory_tenant_filter_is_injected() -> None:
    result = prepare_validated_sql(
        sql="SELECT email FROM public.users",
        allowed_schema=build_allowed_schema(include_row_filter=True),
        tenant_id=TENANT_ID,
        user_id=USER_ID,
        maximum_rows=100,
    )

    assert "WHERE users.tenant_id" in result.sql
    assert str(TENANT_ID) in result.sql
    assert "LIMIT 100" in result.sql
    assert result.row_filters_applied is True


def test_existing_where_and_security_filter_are_combined() -> None:
    result = prepare_validated_sql(
        sql=("SELECT email FROM public.users WHERE email = 'admin@example.com'"),
        allowed_schema=build_allowed_schema(include_row_filter=True),
        tenant_id=TENANT_ID,
        user_id=USER_ID,
        maximum_rows=50,
    )

    assert "admin@example.com" in result.sql
    assert str(TENANT_ID) in result.sql
    assert " AND " in result.sql
    assert "LIMIT 50" in result.sql


def test_unauthorized_column_is_rejected() -> None:
    with pytest.raises(
        QuerySecurityError,
        match="Initial SQL validation failed",
    ):
        prepare_validated_sql(
            sql=("SELECT password_hash FROM public.users"),
            allowed_schema=build_allowed_schema(),
            tenant_id=TENANT_ID,
            user_id=USER_ID,
        )


def test_write_query_is_rejected() -> None:
    with pytest.raises(
        QuerySecurityError,
        match="Initial SQL validation failed",
    ):
        prepare_validated_sql(
            sql=("DELETE FROM public.users WHERE email = 'admin@example.com'"),
            allowed_schema=build_allowed_schema(),
            tenant_id=TENANT_ID,
            user_id=USER_ID,
        )


def test_excessive_limit_is_reduced() -> None:
    result = prepare_validated_sql(
        sql=("SELECT email FROM public.users LIMIT 5000"),
        allowed_schema=build_allowed_schema(),
        tenant_id=TENANT_ID,
        user_id=USER_ID,
        maximum_rows=100,
    )

    assert result.applied_limit == 100
    assert "LIMIT 100" in result.sql
    assert "LIMIT 5000" not in result.sql


def test_empty_permission_schema_is_rejected() -> None:
    with pytest.raises(
        QuerySecurityError,
        match="no readable database tables",
    ):
        prepare_validated_sql(
            sql="SELECT email FROM public.users",
            allowed_schema=AllowedSchema(connection_id="connection-id"),
            tenant_id=TENANT_ID,
            user_id=USER_ID,
        )


def test_select_star_is_rejected() -> None:
    with pytest.raises(
        QuerySecurityError,
        match="SELECT \\* is not allowed",
    ):
        prepare_validated_sql(
            sql="SELECT * FROM public.users",
            allowed_schema=build_allowed_schema(),
            tenant_id=TENANT_ID,
            user_id=USER_ID,
        )


def test_multiple_statements_are_rejected() -> None:
    with pytest.raises(
        QuerySecurityError,
        match="Exactly one SQL statement",
    ):
        prepare_validated_sql(
            sql=("SELECT email FROM public.users; SELECT email FROM public.users"),
            allowed_schema=build_allowed_schema(),
            tenant_id=TENANT_ID,
            user_id=USER_ID,
        )
