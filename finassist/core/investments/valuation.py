from __future__ import annotations

from datetime import date
from decimal import Decimal


def fd_interest(
    principal: Decimal,
    rate_pct: Decimal,
    start_date: date,
    as_of_date: date,
) -> Decimal:
    """Simple interest: principal * (rate/100) * elapsed_years (365 days/year)."""
    if as_of_date < start_date:
        return Decimal("0")
    days = (as_of_date - start_date).days
    elapsed_years = Decimal(days) / Decimal(365)
    return Decimal(principal) * (Decimal(rate_pct) / Decimal(100)) * elapsed_years
