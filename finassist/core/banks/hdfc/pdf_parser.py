from __future__ import annotations

from pathlib import Path

import pandas as pd
import pdfplumber

from core.parsing.bank_config import BankConfig


class HDFCPDFParser:
    """Text-based PDF parser. Scanned PDFs raise (OCR is out of v1 scope)."""

    def __init__(self, config: BankConfig):
        self.config = config

    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".pdf"

    def extract_raw(self, pdf_path: Path) -> pd.DataFrame:
        if not self._is_text_based(pdf_path):
            raise ValueError(
                f"PDF appears scanned/image-based. OCR not supported in v1: {pdf_path}"
            )

        all_rows: list[list[str]] = []
        header: list[str] | None = None

        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables(
                    table_settings={
                        "vertical_strategy": "lines",
                        "horizontal_strategy": "lines",
                        "snap_tolerance": 5,
                        "join_tolerance": 5,
                        "edge_min_length": 10,
                        "min_words_vertical": 2,
                        "min_words_horizontal": 1,
                    }
                )
                for table in tables:
                    if not table:
                        continue
                    for row in table:
                        if header is None and self._is_header_row(row):
                            header = [str(c).strip() if c else "" for c in row]
                            continue
                        if header is None:
                            continue
                        cleaned = [str(c).strip() if c else "" for c in row]
                        cleaned.append(str(page_num))
                        all_rows.append(cleaned)

        if header is None:
            raise ValueError(
                f"Could not detect HDFC table header in PDF. "
                f"Expected patterns: {self.config.header_patterns}"
            )

        header.append("_source_page")
        return pd.DataFrame(all_rows, columns=header)

    def _is_text_based(self, pdf_path: Path) -> bool:
        with pdfplumber.open(str(pdf_path)) as pdf:
            total = 0
            for page in pdf.pages[:3]:
                total += len((page.extract_text() or "").strip())
            return total > 50

    def _is_header_row(self, row: list) -> bool:
        if not row:
            return False
        text = " ".join(str(c).strip().lower() for c in row if c)
        match_count = sum(1 for p in self.config.header_patterns if p.lower() in text)
        return match_count >= 2
