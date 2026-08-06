import uuid
from enum import StrEnum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class RowFilterOperator(StrEnum):
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUAL = "lte"
    IN = "in"
    NOT_IN = "not_in"


class RowFilterValueSource(StrEnum):
    LITERAL = "literal"
    TENANT_ID = "tenant_id"
    USER_ID = "user_id"


class ColumnMaskType(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    EMAIL = "email"
    HASH = "hash"


class RowFilterRule(BaseModel):
    column_id: uuid.UUID
    operator: RowFilterOperator
    value_source: RowFilterValueSource = RowFilterValueSource.LITERAL
    value: Any | None = None

    @model_validator(mode="after")
    def validate_filter_value(self) -> "RowFilterRule":
        if self.value_source == RowFilterValueSource.LITERAL and self.value is None:
            raise ValueError("A literal row filter must include a value.")

        if self.value_source != RowFilterValueSource.LITERAL and self.value is not None:
            raise ValueError(
                "Context-based row filters cannot include a literal value."
            )

        if (
            self.operator
            in {
                RowFilterOperator.IN,
                RowFilterOperator.NOT_IN,
            }
            and self.value_source == RowFilterValueSource.LITERAL
            and not isinstance(self.value, list)
        ):
            raise ValueError("The in and not_in operators require a list value.")

        return self


class RowFilterGroup(BaseModel):
    match: str = Field(
        default="all",
        pattern="^(all|any)$",
    )
    rules: list[RowFilterRule] = Field(
        default_factory=list,
        max_length=20,
    )


class ColumnPermissionInput(BaseModel):
    column_id: uuid.UUID
    can_read: bool = True
    can_filter: bool = True
    can_aggregate: bool = True
    mask_type: ColumnMaskType | None = None

    @model_validator(mode="after")
    def validate_column_rules(
        self,
    ) -> "ColumnPermissionInput":
        if not self.can_read and self.mask_type is not None:
            raise ValueError("A hidden column cannot also have a mask type.")

        return self


class TablePermissionCreate(BaseModel):
    role_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    connection_id: uuid.UUID
    table_id: uuid.UUID

    can_read: bool = True
    can_insert: bool = False
    can_update: bool = False
    can_delete: bool = False

    row_filter: RowFilterGroup = Field(
        default_factory=RowFilterGroup,
    )
    columns: list[ColumnPermissionInput] = Field(
        default_factory=list,
        max_length=500,
    )

    @model_validator(mode="after")
    def validate_subject(self) -> "TablePermissionCreate":
        has_role = self.role_id is not None
        has_user = self.user_id is not None

        if has_role == has_user:
            raise ValueError(
                "Provide exactly one permission subject: role_id or user_id."
            )

        return self


class TablePermissionUpdate(BaseModel):
    can_read: bool | None = None
    can_insert: bool | None = None
    can_update: bool | None = None
    can_delete: bool | None = None
    row_filter: RowFilterGroup | None = None
    columns: list[ColumnPermissionInput] | None = Field(
        default=None,
        max_length=500,
    )


class ColumnPermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    table_permission_id: uuid.UUID
    column_id: uuid.UUID
    can_read: bool
    can_filter: bool
    can_aggregate: bool
    mask_type: str | None


class TablePermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    role_id: uuid.UUID | None
    user_id: uuid.UUID | None
    connection_id: uuid.UUID
    table_id: uuid.UUID
    can_read: bool
    can_insert: bool
    can_update: bool
    can_delete: bool
    row_filter: dict[str, Any]
    columns: list[ColumnPermissionResponse] = Field(
        default_factory=list,
    )


class TablePermissionListResponse(BaseModel):
    items: list[TablePermissionResponse]
    total: int
