from dataclasses import dataclass, field

from sqlglot import exp, parse
from sqlglot.errors import ParseError

from core.permissions import (
    AllowedColumn,
    AllowedSchema,
    AllowedTable,
)


@dataclass(slots=True)
class SQLValidationResult:
    is_valid: bool
    normalized_sql: str | None = None
    errors: list[str] = field(default_factory=list)
    referenced_tables: list[str] = field(default_factory=list)
    referenced_columns: list[str] = field(default_factory=list)
    applied_limit: int | None = None


class SQLValidationError(ValueError):
    """Raised when SQL violates a security rule."""


SYSTEM_SCHEMAS = {
    "information_schema",
    "pg_catalog",
    "pg_toast",
}

COMMENT_MARKERS = (
    "--",
    "/*",
    "*/",
)

BLOCKED_EXPRESSION_KEYS = {
    "alter",
    "command",
    "copy",
    "create",
    "delete",
    "drop",
    "grant",
    "insert",
    "load",
    "merge",
    "revoke",
    "truncate",
    "truncatetable",
    "update",
}


def reject_sql_comments(sql: str) -> None:
    if any(marker in sql for marker in COMMENT_MARKERS):
        raise SQLValidationError("SQL comments are not allowed.")


def parse_single_statement(
    sql: str,
    *,
    dialect: str,
) -> exp.Expression:
    if not sql or not sql.strip():
        raise SQLValidationError("SQL cannot be empty.")

    reject_sql_comments(sql)

    try:
        statements = [
            statement
            for statement in parse(
                sql,
                read=dialect,
            )
            if statement is not None
        ]
    except ParseError as exc:
        raise SQLValidationError("SQL could not be parsed.") from exc

    if len(statements) != 1:
        raise SQLValidationError("Exactly one SQL statement is required.")

    return statements[0]


def validate_read_only_statement(
    statement: exp.Expression,
) -> None:
    if not isinstance(statement, exp.Query):
        raise SQLValidationError("Only SELECT or WITH queries are allowed.")

    for node in statement.walk():
        if node.key.lower() in BLOCKED_EXPRESSION_KEYS:
            raise SQLValidationError("Only read-only SQL queries are allowed.")

    if not any(True for _ in statement.find_all(exp.Select)):
        raise SQLValidationError("The query must contain a SELECT statement.")


def get_cte_names(
    statement: exp.Expression,
) -> set[str]:
    return {
        cte.alias_or_name.lower()
        for cte in statement.find_all(exp.CTE)
        if cte.alias_or_name
    }


def resolve_allowed_table(
    *,
    table: exp.Table,
    allowed_schema: AllowedSchema,
    cte_names: set[str],
) -> tuple[str, AllowedTable] | None:
    table_name = table.name.lower()

    if table_name in cte_names:
        return None

    schema_name = table.db.lower() if table.db else None

    if schema_name in SYSTEM_SCHEMAS:
        raise SQLValidationError("System schemas are not allowed.")

    if schema_name is not None:
        qualified_name = f"{schema_name}.{table_name}"

        allowed_table = allowed_schema.tables.get(qualified_name)

        if allowed_table is None:
            raise SQLValidationError(f"Table '{qualified_name}' is not allowed.")

        return qualified_name, allowed_table

    matching_tables = [
        (qualified_name, allowed_table)
        for qualified_name, allowed_table in allowed_schema.tables.items()
        if allowed_table.table_name.lower() == table_name
    ]

    if not matching_tables:
        raise SQLValidationError(f"Table '{table_name}' is not allowed.")

    if len(matching_tables) > 1:
        raise SQLValidationError(
            f"Table '{table_name}' is ambiguous. Use a schema-qualified table name."
        )

    return matching_tables[0]


def collect_referenced_tables(
    *,
    statement: exp.Expression,
    allowed_schema: AllowedSchema,
) -> tuple[
    list[str],
    dict[str, AllowedTable],
]:
    cte_names = get_cte_names(statement)
    referenced_tables: list[str] = []
    table_lookup: dict[str, AllowedTable] = {}

    for table in statement.find_all(exp.Table):
        resolved_table = resolve_allowed_table(
            table=table,
            allowed_schema=allowed_schema,
            cte_names=cte_names,
        )

        if resolved_table is None:
            continue

        qualified_name, allowed_table = resolved_table

        if qualified_name not in referenced_tables:
            referenced_tables.append(qualified_name)

        table_lookup[qualified_name.lower()] = allowed_table

        table_lookup[allowed_table.table_name.lower()] = allowed_table

        if table.alias:
            table_lookup[table.alias.lower()] = allowed_table

    if not referenced_tables:
        raise SQLValidationError("The query must reference at least one allowed table.")

    return referenced_tables, table_lookup


def reject_star_selection(
    statement: exp.Expression,
) -> None:
    if statement.find(exp.Star) is not None:
        raise SQLValidationError(
            "SELECT * is not allowed. Columns must be selected explicitly."
        )


def resolve_unqualified_column(
    *,
    column_name: str,
    referenced_tables: list[str],
    allowed_schema: AllowedSchema,
) -> tuple[AllowedTable, AllowedColumn]:
    matches: list[tuple[AllowedTable, AllowedColumn]] = []

    for qualified_name in referenced_tables:
        allowed_table = allowed_schema.tables[qualified_name]
        allowed_column = allowed_table.columns.get(column_name)

        if allowed_column is not None:
            matches.append(
                (
                    allowed_table,
                    allowed_column,
                )
            )

    if not matches:
        raise SQLValidationError(f"Column '{column_name}' is not allowed.")

    if len(matches) > 1:
        raise SQLValidationError(
            f"Column '{column_name}' is ambiguous. Use a table-qualified column name."
        )

    return matches[0]


def is_filter_column(
    column: exp.Column,
) -> bool:
    parent = column.parent

    while parent is not None:
        if isinstance(
            parent,
            (
                exp.Where,
                exp.Having,
                exp.Join,
            ),
        ):
            return True

        if isinstance(parent, exp.Select):
            return False

        parent = parent.parent

    return False


def is_aggregate_column(
    column: exp.Column,
) -> bool:
    parent = column.parent

    while parent is not None:
        if isinstance(parent, exp.AggFunc):
            return True

        if isinstance(parent, exp.Select):
            return False

        parent = parent.parent

    return False


def validate_column_access(
    *,
    column: exp.Column,
    allowed_column: AllowedColumn,
) -> None:
    column_name = column.name.lower()

    if not allowed_column.can_read:
        raise SQLValidationError(f"Column '{column_name}' is not readable.")

    if is_filter_column(column) and not allowed_column.can_filter:
        raise SQLValidationError(
            f"Column '{column_name}' cannot be used for filtering."
        )

    if is_aggregate_column(column) and not allowed_column.can_aggregate:
        raise SQLValidationError(f"Column '{column_name}' cannot be aggregated.")


def collect_referenced_columns(
    *,
    statement: exp.Expression,
    referenced_tables: list[str],
    table_lookup: dict[str, AllowedTable],
    allowed_schema: AllowedSchema,
) -> list[str]:
    reject_star_selection(statement)

    referenced_columns: list[str] = []

    for column in statement.find_all(exp.Column):
        column_name = column.name.lower()

        if not column_name:
            continue

        qualifier = column.table.lower() if column.table else None

        if qualifier is not None:
            allowed_table = table_lookup.get(qualifier)

            if allowed_table is None:
                raise SQLValidationError(
                    f"Unknown table or alias '{qualifier}' for column '{column_name}'."
                )

            allowed_column = allowed_table.columns.get(column_name)

            if allowed_column is None:
                raise SQLValidationError(f"Column '{column_name}' is not allowed.")
        else:
            (
                allowed_table,
                allowed_column,
            ) = resolve_unqualified_column(
                column_name=column_name,
                referenced_tables=referenced_tables,
                allowed_schema=allowed_schema,
            )

        validate_column_access(
            column=column,
            allowed_column=allowed_column,
        )

        column_reference = (
            f"{allowed_table.schema_name}.{allowed_table.table_name}.{column_name}"
        )

        if column_reference not in referenced_columns:
            referenced_columns.append(column_reference)

    if not referenced_columns:
        raise SQLValidationError(
            "The query must reference at least one readable column."
        )

    return referenced_columns


def apply_row_limit(
    *,
    statement: exp.Expression,
    maximum_rows: int,
) -> int:
    if maximum_rows < 1:
        raise SQLValidationError("The maximum row limit must be positive.")

    limit_expression = statement.args.get("limit")

    if limit_expression is not None:
        existing_expression = limit_expression.expression

        if isinstance(existing_expression, exp.Literal) and existing_expression.is_int:
            existing_limit = int(existing_expression.this)

            if 1 <= existing_limit <= maximum_rows:
                return existing_limit

    statement.set(
        "limit",
        exp.Limit(expression=exp.Literal.number(maximum_rows)),
    )

    return maximum_rows


def validate_sql(
    *,
    sql: str,
    allowed_schema: AllowedSchema,
    dialect: str = "postgres",
    maximum_rows: int = 100,
) -> SQLValidationResult:
    try:
        statement = parse_single_statement(
            sql,
            dialect=dialect,
        )

        validate_read_only_statement(statement)

        (
            referenced_tables,
            table_lookup,
        ) = collect_referenced_tables(
            statement=statement,
            allowed_schema=allowed_schema,
        )

        referenced_columns = collect_referenced_columns(
            statement=statement,
            referenced_tables=referenced_tables,
            table_lookup=table_lookup,
            allowed_schema=allowed_schema,
        )

        applied_limit = apply_row_limit(
            statement=statement,
            maximum_rows=maximum_rows,
        )

        return SQLValidationResult(
            is_valid=True,
            normalized_sql=statement.sql(
                dialect=dialect,
                pretty=False,
            ),
            referenced_tables=referenced_tables,
            referenced_columns=referenced_columns,
            applied_limit=applied_limit,
        )

    except SQLValidationError as exc:
        return SQLValidationResult(
            is_valid=False,
            errors=[str(exc)],
        )
