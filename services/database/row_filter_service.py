import uuid
from typing import Any

from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

from core.permissions import (
    AllowedColumn,
    AllowedSchema,
    AllowedTable,
)


class RowFilterError(ValueError):
    """Raised when a mandatory row filter cannot be applied safely."""


SUPPORTED_OPERATORS = {
    "eq",
    "ne",
    "gt",
    "gte",
    "lt",
    "lte",
    "in",
    "not_in",
}

SUPPORTED_VALUE_SOURCES = {
    "literal",
    "tenant_id",
    "user_id",
}


def resolve_filter_column(
    *,
    allowed_table: AllowedTable,
    column_id: str,
) -> AllowedColumn:
    for allowed_column in allowed_table.columns.values():
        if allowed_column.column_id == column_id:
            return allowed_column

    raise RowFilterError("A row filter references an unavailable column.")


def resolve_filter_value(
    *,
    rule: dict[str, Any],
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Any:
    value_source = rule.get(
        "value_source",
        "literal",
    )

    if value_source not in SUPPORTED_VALUE_SOURCES:
        raise RowFilterError("The row filter value source is not supported.")

    if value_source == "tenant_id":
        return str(tenant_id)

    if value_source == "user_id":
        return str(user_id)

    if "value" not in rule:
        raise RowFilterError("A literal row filter must contain a value.")

    return rule["value"]


def build_comparison_expression(
    *,
    column_expression: exp.Column,
    operator: str,
    value: Any,
) -> exp.Expression:
    if operator not in SUPPORTED_OPERATORS:
        raise RowFilterError("The row filter operator is not supported.")

    if operator == "in" or operator == "not_in":
        if not isinstance(value, list) or not value:
            raise RowFilterError(
                "The in and not_in operators require a non-empty list."
            )

        in_expression = exp.In(
            this=column_expression,
            expressions=[exp.convert(item) for item in value],
        )

        if operator == "not_in":
            return exp.Not(this=in_expression)

        return in_expression

    value_expression = exp.convert(value)

    if operator == "eq":
        return exp.EQ(
            this=column_expression,
            expression=value_expression,
        )

    if operator == "ne":
        return exp.NEQ(
            this=column_expression,
            expression=value_expression,
        )

    if operator == "gt":
        return exp.GT(
            this=column_expression,
            expression=value_expression,
        )

    if operator == "gte":
        return exp.GTE(
            this=column_expression,
            expression=value_expression,
        )

    if operator == "lt":
        return exp.LT(
            this=column_expression,
            expression=value_expression,
        )

    return exp.LTE(
        this=column_expression,
        expression=value_expression,
    )


def combine_expressions(
    expressions: list[exp.Expression],
    *,
    match: str,
) -> exp.Expression:
    if not expressions:
        raise RowFilterError("A row filter group must contain at least one rule.")

    if match not in {"all", "any"}:
        raise RowFilterError("A row filter group must use all or any matching.")

    combined_expression = expressions[0]

    for expression in expressions[1:]:
        if match == "all":
            combined_expression = exp.and_(
                combined_expression,
                expression,
            )
        else:
            combined_expression = exp.or_(
                combined_expression,
                expression,
            )

    return combined_expression


def build_filter_group_expression(
    *,
    allowed_table: AllowedTable,
    table_reference: str,
    filter_group: dict[str, Any],
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> exp.Expression:
    match = filter_group.get("match", "all")
    rules = filter_group.get("rules")

    if not isinstance(rules, list) or not rules:
        raise RowFilterError("A row filter group must contain rules.")

    expressions: list[exp.Expression] = []

    for rule in rules:
        if not isinstance(rule, dict):
            raise RowFilterError("A row filter rule must be an object.")

        column_id = rule.get("column_id")
        operator = rule.get("operator")

        if not isinstance(column_id, str):
            raise RowFilterError("A row filter rule must contain a column ID.")

        if not isinstance(operator, str):
            raise RowFilterError("A row filter rule must contain an operator.")

        allowed_column = resolve_filter_column(
            allowed_table=allowed_table,
            column_id=column_id,
        )

        value = resolve_filter_value(
            rule=rule,
            tenant_id=tenant_id,
            user_id=user_id,
        )

        column_expression = exp.column(
            allowed_column.name,
            table=table_reference,
        )

        expressions.append(
            build_comparison_expression(
                column_expression=column_expression,
                operator=operator,
                value=value,
            )
        )

    return combine_expressions(
        expressions,
        match=match,
    )


def get_direct_tables(
    select_expression: exp.Select,
) -> list[exp.Table]:
    direct_tables: list[exp.Table] = []

    for table in select_expression.find_all(exp.Table):
        parent_select = table.find_ancestor(exp.Select)

        if parent_select is select_expression:
            direct_tables.append(table)

    return direct_tables


def resolve_select_table(
    *,
    table_expression: exp.Table,
    allowed_schema: AllowedSchema,
) -> tuple[AllowedTable, str] | None:
    table_name = table_expression.name.lower()

    cte_ancestor = table_expression.find_ancestor(exp.CTE)

    if cte_ancestor is not None:
        return None

    schema_name = table_expression.db.lower() if table_expression.db else None

    if schema_name is not None:
        qualified_name = f"{schema_name}.{table_name}"

        allowed_table = allowed_schema.tables.get(qualified_name)

        if allowed_table is None:
            return None
    else:
        matches = [
            allowed_table
            for allowed_table in allowed_schema.tables.values()
            if allowed_table.table_name.lower() == table_name
        ]

        if not matches:
            return None

        if len(matches) > 1:
            raise RowFilterError(f"Table '{table_name}' is ambiguous.")

        allowed_table = matches[0]

    table_reference = table_expression.alias or table_expression.name

    return allowed_table, table_reference


def build_select_security_expression(
    *,
    select_expression: exp.Select,
    allowed_schema: AllowedSchema,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> exp.Expression | None:
    security_expressions: list[exp.Expression] = []

    for table_expression in get_direct_tables(select_expression):
        resolved_table = resolve_select_table(
            table_expression=table_expression,
            allowed_schema=allowed_schema,
        )

        if resolved_table is None:
            continue

        allowed_table, table_reference = resolved_table

        for filter_group in allowed_table.row_filters:
            security_expressions.append(
                build_filter_group_expression(
                    allowed_table=allowed_table,
                    table_reference=table_reference,
                    filter_group=filter_group,
                    tenant_id=tenant_id,
                    user_id=user_id,
                )
            )

    if not security_expressions:
        return None

    return combine_expressions(
        security_expressions,
        match="all",
    )


def inject_filter_into_select(
    *,
    select_expression: exp.Select,
    security_expression: exp.Expression,
) -> None:
    existing_where = select_expression.args.get("where")

    if existing_where is None:
        select_expression.set(
            "where",
            exp.Where(
                this=security_expression,
            ),
        )
        return

    combined_where = exp.and_(
        existing_where.this,
        security_expression,
    )

    select_expression.set(
        "where",
        exp.Where(
            this=combined_where,
        ),
    )


def inject_mandatory_row_filters(
    *,
    sql: str,
    allowed_schema: AllowedSchema,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    dialect: str = "postgres",
) -> str:
    if not sql or not sql.strip():
        raise RowFilterError("SQL cannot be empty.")

    try:
        statement = parse_one(
            sql,
            read=dialect,
        )
    except ParseError as exc:
        raise RowFilterError("SQL could not be parsed for row filtering.") from exc

    select_expressions = list(statement.find_all(exp.Select))

    if isinstance(statement, exp.Select):
        select_expressions.insert(
            0,
            statement,
        )

    unique_selects: list[exp.Select] = []
    seen_select_ids: set[int] = set()

    for select_expression in select_expressions:
        select_identity = id(select_expression)

        if select_identity in seen_select_ids:
            continue

        seen_select_ids.add(select_identity)
        unique_selects.append(select_expression)

    for select_expression in unique_selects:
        security_expression = build_select_security_expression(
            select_expression=select_expression,
            allowed_schema=allowed_schema,
            tenant_id=tenant_id,
            user_id=user_id,
        )

        if security_expression is not None:
            inject_filter_into_select(
                select_expression=select_expression,
                security_expression=security_expression,
            )

    return statement.sql(
        dialect=dialect,
        pretty=False,
    )
