from __future__ import annotations

from decimal import Decimal
from typing import Any

from core.parsing.raw_transaction import RawTransaction


def validate_running_balance(
    transactions: list[RawTransaction],
    opening_balance: Decimal | None = None,
    tolerance: Decimal = Decimal("0.02"),
) -> list[dict[str, Any]]:
    discrepancies: list[dict[str, Any]] = []
    if not transactions:
        return discrepancies

    prev_balance = opening_balance

    for idx, txn in enumerate(transactions):
        if txn.balance_after is None:
            prev_balance = None
            continue

        if prev_balance is not None:
            expected = (
                prev_balance - txn.amount if txn.type == "debit" else prev_balance + txn.amount
            )
            diff = abs(expected - txn.balance_after)
            if diff > tolerance:
                discrepancies.append(
                    {
                        "index": idx,
                        "expected_balance": expected,
                        "actual_balance": txn.balance_after,
                        "difference": diff,
                        "txn_date": txn.txn_date,
                        "narration": txn.narration[:60],
                        "amount": txn.amount,
                        "type": txn.type,
                    }
                )

        prev_balance = txn.balance_after

    return discrepancies
