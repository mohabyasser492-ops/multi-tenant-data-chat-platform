import uuid

import pytest

from core.permissions import (
    AllowedColumn,
    AllowedSchema,
    AllowedTable,
)
from services.database.row_filter_service import (
    RowFilterError,
    inject_mandatory_row_filters,
)

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


def build_allowed_schema(
    *,
    row_filters: list[dict] | None = None,
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
        row_filters=row_filters or [],
    )

    return AllowedSchema(
        connection_id="connection-id",
        tables={
            "public.users": users_table,
        },
    )


def test_query_without_filters_is_unchanged() -> None:
    sql = "SELECT email FROM public.users"

    filtered_sql = inject_mandatory_row_filters(
        sql=sql,
        allowed_schema=build_allowed_schema(),
        tenant_id=TENANT_ID,
        user_id=USER_ID,
    )

    assert filtered_sql == sql


def test_tenant_filter_is_injected() -> None:
    allowed_schema = build_allowed_schema(
        row_filters=[
            {
                "match": "all",
                "rules": [
                    {
                        "column_id": "tenant-column-id",
                        "operator": "eq",
                        "value_source": "tenant_id",
                        "value": None,
                    }
                ],
            }
        ]
    )

    filtered_sql = inject_mandatory_row_filters(
        sql="SELECT email FROM public.users",
        allowed_schema=allowed_schema,
        tenant_id=TENANT_ID,
        user_id=USER_ID,
    )

    assert "WHERE users.tenant_id" in filtered_sql
    assert str(TENANT_ID) in filtered_sql


def test_existing_where_clause_is_preserved() -> None:
    allowed_schema = build_allowed_schema(
        row_filters=[
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
    )

    filtered_sql = inject_mandatory_row_filters(
        sql=("SELECT email FROM public.users WHERE email = 'admin@example.com'"),
        allowed_schema=allowed_schema,
        tenant_id=TENANT_ID,
        user_id=USER_ID,
    )

    assert "admin@example.com" in filtered_sql
    assert str(TENANT_ID) in filtered_sql
    assert " AND " in filtered_sql


def test_table_alias_is_used_in_filter() -> None:
    allowed_schema = build_allowed_schema(
        row_filters=[
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
    )

    filtered_sql = inject_mandatory_row_filters(
        sql="SELECT u.email FROM public.users AS u",
        allowed_schema=allowed_schema,
        tenant_id=TENANT_ID,
        user_id=USER_ID,
    )

    assert "u.tenant_id" in filtered_sql


def test_literal_in_filter_is_injected() -> None:
    allowed_schema = build_allowed_schema(
        row_filters=[
            {
                "match": "all",
                "rules": [
                    {
                        "column_id": "email-column-id",
                        "operator": "in",
                        "value_source": "literal",
                        "value": [
                            "one@example.com",
                            "two@example.com",
                        ],
                    }
                ],
            }
        ]
    )

    filtered_sql = inject_mandatory_row_filters(
        sql="SELECT email FROM public.users",
        allowed_schema=allowed_schema,
        tenant_id=TENANT_ID,
        user_id=USER_ID,
    )

    assert " IN " in filtered_sql
    assert "one@example.com" in filtered_sql
    assert "two@example.com" in filtered_sql


def test_multiple_filter_groups_are_combined_with_and() -> None:
    allowed_schema = build_allowed_schema(
        row_filters=[
            {
                "match": "all",
                "rules": [
                    {
                        "column_id": "tenant-column-id",
                        "operator": "eq",
                        "value_source": "tenant_id",
                    }
                ],
            },
            {
                "match": "all",
                "rules": [
                    {
                        "column_id": "email-column-id",
                        "operator": "ne",
                        "value_source": "literal",
                        "value": "blocked@example.com",
                    }
                ],
            },
        ]
    )

    filtered_sql = inject_mandatory_row_filters(
        sql="SELECT email FROM public.users",
        allowed_schema=allowed_schema,
        tenant_id=TENANT_ID,
        user_id=USER_ID,
    )

    assert str(TENANT_ID) in filtered_sql
    assert "blocked@example.com" in filtered_sql
    assert " AND " in filtered_sql


def test_unknown_filter_column_is_rejected() -> None:
    allowed_schema = build_allowed_schema(
        row_filters=[
            {
                "match": "all",
                "rules": [
                    {
                        "column_id": "unknown-column-id",
                        "operator": "eq",
                        "value_source": "tenant_id",
                    }
                ],
            }
        ]
    )

    with pytest.raises(
        RowFilterError,
        match="unavailable column",
    ):
        inject_mandatory_row_filters(
            sql="SELECT email FROM public.users",
            allowed_schema=allowed_schema,
            tenant_id=TENANT_ID,
            user_id=USER_ID,
        )


def test_invalid_operator_is_rejected() -> None:
    allowed_schema = build_allowed_schema(
        row_filters=[
            {
                "match": "all",
                "rules": [
                    {
                        "column_id": "email-column-id",
                        "operator": "raw_sql",
                        "value_source": "literal",
                        "value": "unsafe",
                    }
                ],
            }
        ]
    )

    with pytest.raises(
        RowFilterError,
        match="operator is not supported",
    ):
        inject_mandatory_row_filters(
            sql="SELECT email FROM public.users",
            allowed_schema=allowed_schema,
            tenant_id=TENANT_ID,
            user_id=USER_ID,
        )


def test_literal_filter_requires_value() -> None:
    allowed_schema = build_allowed_schema(
        row_filters=[
            {
                "match": "all",
                "rules": [
                    {
                        "column_id": "email-column-id",
                        "operator": "eq",
                        "value_source": "literal",
                    }
                ],
            }
        ]
    )

    with pytest.raises(
        RowFilterError,
        match="must contain a value",
    ):
        inject_mandatory_row_filters(
            sql="SELECT email FROM public.users",
            allowed_schema=allowed_schema,
            tenant_id=TENANT_ID,
            user_id=USER_ID,
        )


def test_empty_in_list_is_rejected() -> None:
    allowed_schema = build_allowed_schema(
        row_filters=[
            {
                "match": "all",
                "rules": [
                    {
                        "column_id": "email-column-id",
                        "operator": "in",
                        "value_source": "literal",
                        "value": [],
                    }
                ],
            }
        ]
    )

    with pytest.raises(
        RowFilterError,
        match="non-empty list",
    ):
        inject_mandatory_row_filters(
            sql="SELECT email FROM public.users",
            allowed_schema=allowed_schema,
            tenant_id=TENANT_ID,
            user_id=USER_ID,
        )
