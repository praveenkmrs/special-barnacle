from __future__ import annotations

import pandas as pd

from core.parsing.bank_config import BankConfig
from core.parsing.date_parser import looks_like_date


def merge_multiline_narrations(df: pd.DataFrame, config: BankConfig) -> pd.DataFrame:
    """Merge HDFC's multi-line narrations into single rows.

    Continuation rows have an empty Date cell — append their narration text
    to the most recent date-bearing row's narration.
    """
    if not config.multiline_narration:
        return df

    date_col = config.columns.get("date", "")
    narration_col = config.columns.get("narration", "")
    if not date_col or not narration_col:
        return df

    # Case-insensitive header match
    if date_col not in df.columns or narration_col not in df.columns:
        for col in df.columns:
            if col.strip().lower() == date_col.strip().lower():
                date_col = col
            if col.strip().lower() == narration_col.strip().lower():
                narration_col = col

    if date_col not in df.columns or narration_col not in df.columns:
        return df

    merged_rows: list[pd.Series] = []
    current: pd.Series | None = None

    for _, row in df.iterrows():
        date_value = str(row.get(date_col, "")).strip()
        if looks_like_date(date_value):
            if current is not None:
                merged_rows.append(current)
            current = row.copy()
        else:
            if current is not None:
                continuation = str(row.get(narration_col, "")).strip()
                if continuation and continuation.lower() != "nan":
                    existing = str(current[narration_col]).strip()
                    current[narration_col] = f"{existing} {continuation}".strip()

    if current is not None:
        merged_rows.append(current)

    if not merged_rows:
        return df.iloc[0:0]
    return pd.DataFrame(merged_rows).reset_index(drop=True)
