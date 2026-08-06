import uuid

import pytest
from pydantic import ValidationError

from schemas.permission import (
    ColumnMaskType,
    ColumnPermissionInput,
    RowFilterGroup,
    RowFilterOperator,
    RowFilterRule,
    RowFilterValueSource,
    TablePermissionCreate,
)


def test_permission_accepts_role_subject() -> None:
    request = TablePermissionCreate(
        role_id=uuid.uuid4(),
        connection_id=uuid.uuid4(),
        table_id=uuid.uuid4(),
    )

    assert request.role_id is not None
    assert request.user_id is None


def test_permission_accepts_user_subject() -> None:
    request = TablePermissionCreate(
        user_id=uuid.uuid4(),
        connection_id=uuid.uuid4(),
        table_id=uuid.uuid4(),
    )

    assert request.user_id is not None
    assert request.role_id is None


def test_permission_requires_exactly_one_subject() -> None:
    with pytest.raises(
        ValidationError,
        match="exactly one permission subject",
    ):
        TablePermissionCreate(
            connection_id=uuid.uuid4(),
            table_id=uuid.uuid4(),
        )


def test_permission_rejects_two_subjects() -> None:
    with pytest.raises(
        ValidationError,
        match="exactly one permission subject",
    ):
        TablePermissionCreate(
            role_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            connection_id=uuid.uuid4(),
            table_id=uuid.uuid4(),
        )


def test_literal_filter_requires_value() -> None:
    with pytest.raises(
        ValidationError,
        match="must include a value",
    ):
        RowFilterRule(
            column_id=uuid.uuid4(),
            operator=RowFilterOperator.EQUALS,
            value_source=RowFilterValueSource.LITERAL,
        )


def test_context_filter_rejects_literal_value() -> None:
    with pytest.raises(
        ValidationError,
        match="cannot include a literal value",
    ):
        RowFilterRule(
            column_id=uuid.uuid4(),
            operator=RowFilterOperator.EQUALS,
            value_source=RowFilterValueSource.TENANT_ID,
            value="unsafe-value",
        )


def test_in_operator_requires_list() -> None:
    with pytest.raises(
        ValidationError,
        match="require a list value",
    ):
        RowFilterRule(
            column_id=uuid.uuid4(),
            operator=RowFilterOperator.IN,
            value_source=RowFilterValueSource.LITERAL,
            value="not-a-list",
        )


def test_valid_tenant_filter() -> None:
    rule = RowFilterRule(
        column_id=uuid.uuid4(),
        operator=RowFilterOperator.EQUALS,
        value_source=RowFilterValueSource.TENANT_ID,
    )

    assert rule.value is None
    assert rule.value_source == RowFilterValueSource.TENANT_ID


def test_valid_literal_list_filter() -> None:
    rule = RowFilterRule(
        column_id=uuid.uuid4(),
        operator=RowFilterOperator.IN,
        value_source=RowFilterValueSource.LITERAL,
        value=["active", "pending"],
    )

    assert rule.value == ["active", "pending"]


def test_hidden_column_cannot_be_masked() -> None:
    with pytest.raises(
        ValidationError,
        match="hidden column cannot",
    ):
        ColumnPermissionInput(
            column_id=uuid.uuid4(),
            can_read=False,
            mask_type=ColumnMaskType.FULL,
        )


def test_permission_serializes_structured_row_filter() -> None:
    column_id = uuid.uuid4()

    request = TablePermissionCreate(
        role_id=uuid.uuid4(),
        connection_id=uuid.uuid4(),
        table_id=uuid.uuid4(),
        row_filter=RowFilterGroup(
            match="all",
            rules=[
                RowFilterRule(
                    column_id=column_id,
                    operator=RowFilterOperator.EQUALS,
                    value_source=(RowFilterValueSource.TENANT_ID),
                )
            ],
        ),
    )

    serialized = request.model_dump(mode="json")

    assert serialized["row_filter"]["match"] == "all"
    assert serialized["row_filter"]["rules"][0]["column_id"] == str(column_id)
    assert serialized["row_filter"]["rules"][0]["value_source"] == "tenant_id"
