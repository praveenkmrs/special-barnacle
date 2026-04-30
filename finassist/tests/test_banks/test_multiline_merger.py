from __future__ import annotations

import pandas as pd

from core.banks.hdfc.config import HDFC_SAVINGS
from core.banks.hdfc.multiline_merger import merge_multiline_narrations


def _df(rows: list[list[str]]) -> pd.DataFrame:
    header, *data = rows
    return pd.DataFrame(data, columns=header)


def test_three_transactions_merged_from_eight_rows(hdfc_pdf_text_lines) -> None:
    df = _df(hdfc_pdf_text_lines)
    merged = merge_multiline_narrations(df, HDFC_SAVINGS)
    assert len(merged) == 3
    assert "12345" in merged.iloc[0]["Narration"]
    assert "ACME" in merged.iloc[1]["Narration"]
    assert "HDFC0001234" in merged.iloc[1]["Narration"]
    assert "BLR" in merged.iloc[2]["Narration"]


def test_no_op_when_disabled(hdfc_pdf_text_lines) -> None:
    df = _df(hdfc_pdf_text_lines)
    cfg = HDFC_SAVINGS
    cfg_copy = type(cfg)(
        bank_code=cfg.bank_code,
        bank_name=cfg.bank_name,
        account_type=cfg.account_type,
        columns=cfg.columns,
        date_format=cfg.date_format,
        date_format_alt=cfg.date_format_alt,
        multiline_narration=False,
        detection_patterns=cfg.detection_patterns,
        header_patterns=cfg.header_patterns,
    )
    merged = merge_multiline_narrations(df, cfg_copy)
    assert len(merged) == len(df)


def test_orphan_continuation_dropped() -> None:
    df = pd.DataFrame(
        [
            ["", "orphan continuation", "", "", "", "", ""],
            ["01/01/24", "real txn", "", "01/01/24", "100.00", "", "99,900"],
        ],
        columns=[
            "Date",
            "Narration",
            "Chq./Ref.No.",
            "Value Dt",
            "Withdrawal Amt.",
            "Deposit Amt.",
            "Closing Balance",
        ],
    )
    merged = merge_multiline_narrations(df, HDFC_SAVINGS)
    assert len(merged) == 1
    assert merged.iloc[0]["Narration"] == "real txn"


def test_nan_continuation_skipped() -> None:
    df = pd.DataFrame(
        [
            ["01/01/24", "real txn", "", "01/01/24", "100.00", "", "99,900"],
            ["", "nan", "", "", "", "", ""],
        ],
        columns=[
            "Date",
            "Narration",
            "Chq./Ref.No.",
            "Value Dt",
            "Withdrawal Amt.",
            "Deposit Amt.",
            "Closing Balance",
        ],
    )
    merged = merge_multiline_narrations(df, HDFC_SAVINGS)
    assert len(merged) == 1
    assert merged.iloc[0]["Narration"] == "real txn"
