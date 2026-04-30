from __future__ import annotations

from core.parsing.bank_config import BankConfig

HDFC_SAVINGS = BankConfig(
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
    currency="INR",
    multiline_narration=True,
    narration_merge_strategy="concat_until_next_date",
    detection_patterns=[
        "HDFC BANK",
        "Statement of account",
        "Withdrawal Amt.",
        "Narration",
    ],
    header_patterns=["Date", "Narration", "Withdrawal"],
    password_hint="Enter your 9-digit HDFC Customer ID",
)
