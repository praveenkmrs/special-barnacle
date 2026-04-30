from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

import pandas as pd

from core.parsing.amount_parser import parse_indian_amount
from core.parsing.bank_config import BankConfig
from core.parsing.date_parser import parse_date
from core.parsing.raw_transaction import RawTransaction


def normalize_dataframe(
    df: pd.DataFrame,
    config: BankConfig,
    *,
    account_id: int,
    source_file: str = "",
) -> tuple[list[RawTransaction], list[dict[str, Any]]]:
    """Convert a raw bank DataFrame into RawTransaction objects."""
    transactions: list[RawTransaction] = []
    skipped: list[dict[str, Any]] = []

    col_map = config.columns

    for idx, row in df.iterrows():
        try:
            raw_date_str = str(row.get(col_map.get("date", ""), "")).strip()
            txn_date = parse_date(
                raw_date_str,
                primary_format=config.date_format,
                fallback_format=config.date_format_alt,
            )
            if txn_date is None:
                skipped.append({"index": idx, "reason": "unparseable date", "raw": dict(row)})
                continue

            value_date = None
            vd_col = col_map.get("value_date", "")
            if vd_col and vd_col in df.columns:
                vd_str = str(row.get(vd_col, "")).strip()
                value_date = parse_date(vd_str, config.date_format, config.date_format_alt)

            debit_str = str(row.get(col_map.get("debit", ""), "")).strip()
            credit_str = str(row.get(col_map.get("credit", ""), "")).strip()
            balance_str = str(row.get(col_map.get("balance", ""), "")).strip()

            debit_amt = parse_indian_amount(debit_str)
            credit_amt = parse_indian_amount(credit_str)
            balance = parse_indian_amount(balance_str) if balance_str else None

            if debit_amt > 0 and credit_amt == 0:
                txn_type, amount = "debit", debit_amt
                raw_amount_str = debit_str
            elif credit_amt > 0 and debit_amt == 0:
                txn_type, amount = "credit", credit_amt
                raw_amount_str = credit_str
            elif debit_amt > 0 and credit_amt > 0:
                if debit_amt > credit_amt:
                    txn_type, amount = "debit", debit_amt - credit_amt
                else:
                    txn_type, amount = "credit", credit_amt - debit_amt
                raw_amount_str = f"D:{debit_str}|C:{credit_str}"
            else:
                skipped.append({"index": idx, "reason": "zero amount row", "raw": dict(row)})
                continue

            raw_narration = str(row.get(col_map.get("narration", ""), "")).strip()
            narration = _clean_narration(raw_narration)

            reference: str | None = None
            ref_col = col_map.get("reference", "")
            if ref_col and ref_col in df.columns:
                ref = str(row.get(ref_col, "")).strip()
                if ref and ref.lower() != "nan":
                    reference = ref

            source_page = None
            if "_source_page" in df.columns:
                try:
                    source_page = int(row["_source_page"])
                except (ValueError, TypeError):
                    pass

            txn = RawTransaction(
                txn_date=txn_date,
                amount=amount,
                type=txn_type,  # type: ignore[arg-type]
                narration=narration,
                balance_after=balance
                if balance is not None and balance != Decimal("0.00")
                else None,
                account_id=account_id,
                bank_code=config.bank_code,
                reference=reference,
                value_date=value_date,
                source_file=source_file,
                source_page=source_page,
                source_line=int(idx) + 1,
                raw_narration=raw_narration,
                raw_date_str=raw_date_str,
                raw_amount_str=raw_amount_str,
                currency=config.currency,
            )
            txn.compute_hash()
            transactions.append(txn)

        except Exception as e:  # noqa: BLE001
            skipped.append({"index": idx, "reason": f"exception: {e}", "raw": dict(row)})

    return transactions, skipped


def _clean_narration(narration: str) -> str:
    if not narration or narration.lower() == "nan":
        return ""
    cleaned = re.sub(r"\s+", " ", narration).strip()
    cleaned = re.sub(r"\bnan\b", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned
