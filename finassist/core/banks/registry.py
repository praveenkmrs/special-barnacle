from __future__ import annotations

from pathlib import Path

import pdfplumber

from core.banks.base import BankAdapter
from core.banks.hdfc.adapter import HDFCAdapter

ADAPTERS: list[BankAdapter] = [HDFCAdapter()]


def detect_bank(file_path: Path) -> BankAdapter | None:
    for adapter in ADAPTERS:
        try:
            if adapter.detect(file_path):
                return adapter
        except Exception:  # noqa: BLE001
            continue
    return None


def get_adapter_by_code(bank_code: str) -> BankAdapter | None:
    for adapter in ADAPTERS:
        if adapter.bank_code == bank_code:
            return adapter
    return None


def _extract_sample_text(file_path: Path) -> str:
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        try:
            with pdfplumber.open(str(file_path)) as pdf:
                text = ""
                for page in pdf.pages[:2]:
                    text += (page.extract_text() or "") + "\n"
                return text
        except Exception:  # noqa: BLE001
            return ""

    if suffix in (".csv", ".tsv", ".txt"):
        try:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                return "".join(f.readline() for _ in range(20))
        except Exception:  # noqa: BLE001
            return ""

    if suffix in (".xls", ".xlsx"):
        try:
            import pandas as pd

            df = pd.read_excel(file_path, nrows=5, dtype=str)
            return " ".join(df.columns) + " " + df.to_string()
        except Exception:  # noqa: BLE001
            return ""

    return ""
