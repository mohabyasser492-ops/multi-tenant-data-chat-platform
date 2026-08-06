import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from core.permissions import (
    AllowedColumn,
    AllowedSchema,
    AllowedTable,
)
from services.database.query_executor import (
    QueryExecutionError,
    apply_mask,
    calculate_result_size,
    get_column_masks,
    mask_email,
    mask_full,
    mask_hash,
    mask_partial,
    serialize_database_value,
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


def test_serialize_uuid() -> None:
    value = uuid.uuid4()

    assert serialize_database_value(value) == str(value)


def test_serialize_datetime() -> None:
    value = datetime.now(UTC)

    assert (
        serialize_database_value(value)
        == value.isoformat()
    )


def test_serialize_decimal() -> None:
    assert (
        serialize_database_value(
            Decimal("123.45")
        )
        == "123.45"
    )


def test_full_mask() -> None:
    assert mask_full("secret-value") == "********"
    assert mask_full(None) is None


def test_partial_mask() -> None:
    assert mask_partial("12345678") == "12****78"
    assert mask_partial("123") == "***"
    assert mask_partial(None) is None


def test_email_mask() -> None:
    masked = mask_email(
        "admin@example.com"
    )

    assert masked is not None
    assert masked.endswith("@example.com")
    assert "admin@example.com" not in masked


def test_hash_mask_is_stable() -> None:
    first_hash = mask_hash("secret")
    second_hash = mask_hash("secret")

    assert first_hash == second_hash
    assert first_hash is not None
    assert len(first_hash) == 64


def test_apply_unknown_mask_is_rejected() -> None:
    with pytest.raises(
        QueryExecutionError,
        match="mask is not supported",
    ):
        apply_mask(
            "secret",
            "unsupported-mask",
        )


def test_column_masks_are_created_from_permissions() -> None:
    masks = get_column_masks(
        build_allowed_schema()
    )

    assert masks == {
        "email": "email",
    }


def test_result_size_is_measured_in_bytes() -> None:
    result_size = calculate_result_size(
        columns=["email"],
        rows=[
            {
                "email": "a@example.com",
            }
        ],
    )

    assert result_size > 0


def test_nested_values_are_serialized() -> None:
    value = {
        "id": uuid.UUID(
            "11111111-1111-1111-1111-111111111111"
        ),
        "amounts": [
            Decimal("10.50"),
            Decimal("20.75"),
        ],
    }

    serialized = serialize_database_value(value)

    assert serialized == {
        "id": (
            "11111111-1111-1111-1111-111111111111"
        ),
        "amounts": [
            "10.50",
            "20.75",
        ],
    }