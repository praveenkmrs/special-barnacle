from __future__ import annotations

import csv
from pathlib import Path

import pytest


@pytest.fixture
def hdfc_csv_simple(tmp_path: Path) -> Path:
    """Minimal HDFC CSV with single-line narrations covering common patterns."""
    file_path = tmp_path / "hdfc_simple.csv"
    rows = [
        [
            "Date",
            "Narration",
            "Chq./Ref.No.",
            "Value Dt",
            "Withdrawal Amt.",
            "Deposit Amt.",
            "Closing Balance",
        ],
        [
            "01/01/24",
            "UPI-JOHN DOE-OKICICI-12345-",
            "00001234",
            "01/01/24",
            "500.00",
            "",
            "49,500.00",
        ],
        [
            "02/01/24",
            "NEFT-EMP123-ACME PVT LTD-HDFC0001234-SAL",
            "00005678",
            "02/01/24",
            "",
            "50,000.00",
            "99,500.00",
        ],
        [
            "03/01/24",
            "ATW-XXXXXX1234-NS BLR",
            "",
            "03/01/24",
            "2,000.00",
            "",
            "97,500.00",
        ],
        [
            "05/01/24",
            "UPI-SWIGGY-YESB0001-67890-",
            "00006789",
            "05/01/24",
            "350.00",
            "",
            "97,150.00",
        ],
    ]
    with open(file_path, "w", newline="") as f:
        csv.writer(f).writerows(rows)
    return file_path


@pytest.fixture
def hdfc_pdf_text_lines() -> list[list[str]]:
    """Sample HDFC PDF table rows (multi-line narrations) for merger tests."""
    return [
        ["Date", "Narration", "Chq./Ref.No.", "Value Dt", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"],
        ["01/01/24", "UPI-JOHN DOE-OKICICI", "REF1", "01/01/24", "500.00", "", "49,500.00"],
        ["", "-12345-PAYMENT", "", "", "", "", ""],
        ["02/01/24", "NEFT-SALARY", "REF2", "02/01/24", "", "50,000.00", "99,500.00"],
        ["", "ACME PVT LTD", "", "", "", "", ""],
        ["", "HDFC0001234", "", "", "", "", ""],
        ["03/01/24", "ATW-XXXXXX-NS", "", "03/01/24", "2,000.00", "", "97,500.00"],
        ["", "BLR", "", "", "", "", ""],
    ]
