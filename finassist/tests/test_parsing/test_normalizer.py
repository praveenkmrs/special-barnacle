from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd

from core.parsing.bank_config import BankConfig
from core.parsing.normalizer import normalize_dataframe


def _hdfc_config() -> BankConfig:
    return BankConfig(
        bank_code="HDFC",
        bank_name="HDFC Bank",
        account_type="savings",
        columns={
            "date": "Date",
            "narration": "Narration",
            "reference": "Chq./Ref.No.",
            "value_date": "Value Dt",
            "debit": "Withdrawal Amt.",
            "credit": "Deposit Amt.",
            "balance": "Closing Balance",
        },
        date_format="%d/%m/%y",
        date_format_alt="%d/%m/%Y",
    )


def _df(rows: list[dict[str, str]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_basic_debit_and_credit() -> None:
    df = _df(
        [
            {
                "Date": "01/01/24",
                "Narration": "UPI-MERCHANT-ICIC0001-12345-",
                "Chq./Ref.No.": "REF1",
                "Value Dt": "01/01/24",
                "Withdrawal Amt.": "500.00",
                "Deposit Amt.": "",
                "Closing Balance": "49,500.00",
            },
            {
                "Date": "02/01/24",
                "Narration": "NEFT-SALARY-COMPANY",
                "Chq./Ref.No.": "REF2",
                "Value Dt": "02/01/24",
                "Withdrawal Amt.": "",
                "Deposit Amt.": "50,000.00",
                "Closing Balance": "99,500.00",
            },
        ]
    )
    txns, skipped = normalize_dataframe(df, _hdfc_config(), account_id=1, source_file="t.csv")
    assert len(txns) == 2
    assert skipped == []
    assert txns[0].type == "debit" and txns[0].amount == Decimal("500.00")
    assert txns[0].txn_date == date(2024, 1, 1)
    assert txns[0].reference == "REF1"
    assert txns[0].balance_after == Decimal("49500.00")
    assert txns[1].type == "credit" and txns[1].amount == Decimal("50000.00")


def test_zero_amount_row_skipped() -> None:
    df = _df(
        [
            {
                "Date": "01/01/24",
                "Narration": "OPENING BALANCE",
                "Chq./Ref.No.": "",
                "Value Dt": "01/01/24",
                "Withdrawal Amt.": "",
                "Deposit Amt.": "",
                "Closing Balance": "10,000.00",
            }
        ]
    )
    txns, skipped = normalize_dataframe(df, _hdfc_config(), account_id=1)
    assert len(txns) == 0
    assert len(skipped) == 1


def test_unparseable_date_skipped() -> None:
    df = _df(
        [
            {
                "Date": "garbage",
                "Narration": "X",
                "Chq./Ref.No.": "",
                "Value Dt": "",
                "Withdrawal Amt.": "100",
                "Deposit Amt.": "",
                "Closing Balance": "",
            }
        ]
    )
    txns, skipped = normalize_dataframe(df, _hdfc_config(), account_id=1)
    assert len(txns) == 0
    assert skipped[0]["reason"] == "unparseable date"


def test_narration_cleaning_strips_nan() -> None:
    df = _df(
        [
            {
                "Date": "01/01/24",
                "Narration": "UPI-FOO  nan  BAR",
                "Chq./Ref.No.": "",
                "Value Dt": "",
                "Withdrawal Amt.": "100",
                "Deposit Amt.": "",
                "Closing Balance": "",
            }
        ]
    )
    txns, _ = normalize_dataframe(df, _hdfc_config(), account_id=1)
    assert "nan" not in txns[0].narration.lower()
    assert txns[0].narration == "UPI-FOO BAR"


def test_hash_stability_and_difference() -> None:
    df = _df(
        [
            {
                "Date": "01/01/24",
                "Narration": "UPI-A",
                "Chq./Ref.No.": "",
                "Value Dt": "",
                "Withdrawal Amt.": "100",
                "Deposit Amt.": "",
                "Closing Balance": "",
            },
            {
                "Date": "02/01/24",
                "Narration": "UPI-A",
                "Chq./Ref.No.": "",
                "Value Dt": "",
                "Withdrawal Amt.": "200",
                "Deposit Amt.": "",
                "Closing Balance": "",
            },
            {
                "Date": "03/01/24",
                "Narration": "UPI-B",
                "Chq./Ref.No.": "",
                "Value Dt": "",
                "Withdrawal Amt.": "300",
                "Deposit Amt.": "",
                "Closing Balance": "",
            },
        ]
    )
    txns, _ = normalize_dataframe(df, _hdfc_config(), account_id=1)
    assert txns[0].narration_hash == txns[1].narration_hash
    assert txns[0].narration_hash != txns[2].narration_hash


def test_both_debit_and_credit_populated_handled() -> None:
    df = _df(
        [
            {
                "Date": "01/01/24",
                "Narration": "WEIRD",
                "Chq./Ref.No.": "",
                "Value Dt": "",
                "Withdrawal Amt.": "500",
                "Deposit Amt.": "200",
                "Closing Balance": "",
            }
        ]
    )
    txns, _ = normalize_dataframe(df, _hdfc_config(), account_id=1)
    assert len(txns) == 1
    assert txns[0].type == "debit"
    assert txns[0].amount == Decimal("300")
