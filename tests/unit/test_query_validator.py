from core.permissions import (
    AllowedColumn,
    AllowedSchema,
    AllowedTable,
)
from services.database.query_validator import (
    validate_sql,
)


def build_allowed_schema() -> AllowedSchema:
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
            "email": email_column,
        },
    )

    return AllowedSchema(
        connection_id="connection-id",
        tables={
            "public.users": users_table,
        },
    )


def test_valid_select_is_allowed() -> None:
    result = validate_sql(
        sql="SELECT email FROM public.users",
        allowed_schema=build_allowed_schema(),
        maximum_rows=100,
    )

    assert result.is_valid is True
    assert result.applied_limit == 100
    assert result.referenced_tables == ["public.users"]
    assert result.referenced_columns == ["public.users.email"]
    assert result.normalized_sql is not None
    assert "LIMIT 100" in result.normalized_sql


def test_existing_lower_limit_is_preserved() -> None:
    result = validate_sql(
        sql=("SELECT email FROM public.users LIMIT 10"),
        allowed_schema=build_allowed_schema(),
        maximum_rows=100,
    )

    assert result.is_valid is True
    assert result.applied_limit == 10
    assert result.normalized_sql is not None
    assert "LIMIT 10" in result.normalized_sql


def test_excessive_limit_is_reduced() -> None:
    result = validate_sql(
        sql=("SELECT email FROM public.users LIMIT 500"),
        allowed_schema=build_allowed_schema(),
        maximum_rows=100,
    )

    assert result.is_valid is True
    assert result.applied_limit == 100
    assert result.normalized_sql is not None
    assert "LIMIT 100" in result.normalized_sql


def test_select_star_is_rejected() -> None:
    result = validate_sql(
        sql="SELECT * FROM public.users",
        allowed_schema=build_allowed_schema(),
    )

    assert result.is_valid is False
    assert "SELECT * is not allowed" in result.errors[0]


def test_unauthorized_column_is_rejected() -> None:
    result = validate_sql(
        sql="SELECT password_hash FROM public.users",
        allowed_schema=build_allowed_schema(),
    )

    assert result.is_valid is False
    assert "not allowed" in result.errors[0]


def test_unauthorized_table_is_rejected() -> None:
    result = validate_sql(
        sql="SELECT email FROM public.admins",
        allowed_schema=build_allowed_schema(),
    )

    assert result.is_valid is False
    assert "not allowed" in result.errors[0]


def test_system_schema_is_rejected() -> None:
    result = validate_sql(
        sql=("SELECT tablename FROM pg_catalog.pg_tables"),
        allowed_schema=build_allowed_schema(),
    )

    assert result.is_valid is False
    assert "System schemas" in result.errors[0]


def test_multiple_statements_are_rejected() -> None:
    result = validate_sql(
        sql=("SELECT email FROM public.users; SELECT email FROM public.users"),
        allowed_schema=build_allowed_schema(),
    )

    assert result.is_valid is False
    assert "Exactly one SQL statement" in result.errors[0]


def test_sql_comments_are_rejected() -> None:
    result = validate_sql(
        sql=("SELECT email FROM public.users -- unsafe comment"),
        allowed_schema=build_allowed_schema(),
    )

    assert result.is_valid is False
    assert "comments are not allowed" in result.errors[0]


def test_delete_is_rejected() -> None:
    result = validate_sql(
        sql="DELETE FROM public.users",
        allowed_schema=build_allowed_schema(),
    )

    assert result.is_valid is False
    assert "Only SELECT or WITH" in result.errors[0]


def test_update_is_rejected() -> None:
    result = validate_sql(
        sql=("UPDATE public.users SET email = 'changed@example.com'"),
        allowed_schema=build_allowed_schema(),
    )

    assert result.is_valid is False
    assert "Only SELECT or WITH" in result.errors[0]


def test_filterable_column_is_allowed() -> None:
    result = validate_sql(
        sql=("SELECT email FROM public.users WHERE email = 'admin@example.com'"),
        allowed_schema=build_allowed_schema(),
    )

    assert result.is_valid is True


def test_non_aggregate_column_cannot_be_aggregated() -> None:
    result = validate_sql(
        sql=("SELECT COUNT(email) FROM public.users"),
        allowed_schema=build_allowed_schema(),
    )

    assert result.is_valid is False
    assert "cannot be aggregated" in result.errors[0]
