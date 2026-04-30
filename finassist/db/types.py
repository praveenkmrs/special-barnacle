from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import Dialect, String, TypeDecorator


class DecimalText(TypeDecorator[Decimal]):
    """Store Decimal values as TEXT in SQLite to preserve precision."""

    impl = String
    cache_ok = True

    def process_bind_param(
        self, value: Decimal | str | int | float | None, dialect: Dialect
    ) -> str | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return str(value)
        return str(Decimal(str(value)))

    def process_result_value(self, value: Any, dialect: Dialect) -> Decimal | None:
        if value is None:
            return None
        return Decimal(str(value))
