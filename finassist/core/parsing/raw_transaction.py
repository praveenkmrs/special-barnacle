from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

TxnType = Literal["debit", "credit"]


@dataclass
class RawTransaction:
    txn_date: date
    amount: Decimal
    type: TxnType
    narration: str
    balance_after: Decimal | None

    account_id: int
    bank_code: str = "HDFC"

    reference: str | None = None
    value_date: date | None = None

    source_file: str = ""
    source_page: int | None = None
    source_line: int | None = None

    raw_narration: str = ""
    raw_date_str: str = ""
    raw_amount_str: str = ""

    narration_hash: str = ""
    currency: str = "INR"

    def compute_hash(self) -> str:
        normalized = _normalize_for_hash(self.narration)
        self.narration_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return self.narration_hash


def _normalize_for_hash(narration: str) -> str:
    if not narration:
        return ""
    return re.sub(r"\s+", " ", narration.lower()).strip()
