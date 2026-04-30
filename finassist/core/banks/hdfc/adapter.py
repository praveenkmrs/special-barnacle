from __future__ import annotations

from datetime import date
from pathlib import Path

from core.banks.base import BankAdapter
from core.banks.hdfc.config import HDFC_SAVINGS
from core.banks.hdfc.csv_parser import HDFCCSVParser
from core.banks.hdfc.multiline_merger import merge_multiline_narrations
from core.banks.hdfc.pdf_parser import HDFCPDFParser
from core.parsing.decryptor import decrypt_pdf
from core.parsing.normalizer import normalize_dataframe
from core.parsing.raw_transaction import RawTransaction


class HDFCAdapter(BankAdapter):
    bank_code = "HDFC"
    display_name = "HDFC Bank"
    supported_formats = ["pdf", "csv"]

    def __init__(self) -> None:
        self.config = HDFC_SAVINGS
        self.pdf_parser = HDFCPDFParser(self.config)
        self.csv_parser = HDFCCSVParser(self.config)

    def detect(self, file_path: Path) -> bool:
        from core.banks.registry import _extract_sample_text

        text = _extract_sample_text(file_path).lower()
        if not text:
            return False
        match_count = sum(
            1 for pattern in self.config.detection_patterns if pattern.lower() in text
        )
        return match_count >= 2

    def parse(
        self,
        file_path: Path,
        password: str | None = None,
        *,
        account_id: int,
    ) -> list[RawTransaction]:
        suffix = file_path.suffix.lower()

        if suffix == ".pdf":
            decrypted = decrypt_pdf(file_path, password=password)
            df_raw = self.pdf_parser.extract_raw(decrypted)
            df_merged = merge_multiline_narrations(df_raw, self.config)
        elif suffix in (".csv", ".tsv", ".txt"):
            df_raw = self.csv_parser.extract_raw(file_path)
            df_merged = df_raw
        else:
            raise ValueError(f"HDFCAdapter does not support {suffix}")

        transactions, _skipped = normalize_dataframe(
            df_merged,
            self.config,
            account_id=account_id,
            source_file=file_path.name,
        )
        return transactions

    def statement_period(
        self, file_path: Path, password: str | None = None
    ) -> tuple[date, date]:
        txns = self.parse(file_path, password=password, account_id=0)
        if not txns:
            raise ValueError("No transactions found; cannot determine period.")
        dates = [t.txn_date for t in txns]
        return min(dates), max(dates)
