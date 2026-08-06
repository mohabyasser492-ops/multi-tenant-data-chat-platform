from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AllowedColumn:
    column_id: str
    name: str
    data_type: str
    can_read: bool
    can_filter: bool
    can_aggregate: bool
    mask_type: str | None


@dataclass(slots=True)
class AllowedTable:
    table_id: str
    schema_name: str
    table_name: str
    can_read: bool
    can_insert: bool
    can_update: bool
    can_delete: bool
    columns: dict[str, AllowedColumn] = field(default_factory=dict)
    row_filters: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class AllowedSchema:
    connection_id: str
    tables: dict[str, AllowedTable] = field(default_factory=dict)

    def to_prompt_dict(self) -> dict[str, Any]:
        return {
            "connection_id": self.connection_id,
            "tables": {
                qualified_name: {
                    "table_id": table.table_id,
                    "schema_name": table.schema_name,
                    "table_name": table.table_name,
                    "access": {
                        "read": table.can_read,
                        "insert": table.can_insert,
                        "update": table.can_update,
                        "delete": table.can_delete,
                    },
                    "columns": {
                        column_name: {
                            "column_id": column.column_id,
                            "data_type": column.data_type,
                            "can_read": column.can_read,
                            "can_filter": column.can_filter,
                            "can_aggregate": column.can_aggregate,
                            "mask_type": column.mask_type,
                        }
                        for column_name, column in table.columns.items()
                    },
                    "row_filters": table.row_filters,
                }
                for qualified_name, table in self.tables.items()
            },
        }
