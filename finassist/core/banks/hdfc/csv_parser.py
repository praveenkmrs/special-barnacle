from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.parsing.bank_config import BankConfig


class HDFCCSVParser:
    def __init__(self, config: BankConfig):
        self.config = config

    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in (".csv", ".tsv", ".txt")

    def extract_raw(self, file_path: Path) -> pd.DataFrame:
        encoding = self._detect_encoding(file_path)
        delimiter = self._detect_delimiter(file_path, encoding)
        df = pd.read_csv(
            file_path,
            delimiter=delimiter,
            encoding=encoding,
            dtype=str,
            keep_default_na=False,
            skipinitialspace=True,
        )
        df.columns = [c.strip() for c in df.columns]
        df = df.dropna(how="all")
        df = df[~df.apply(lambda row: all(str(v).strip() == "" for v in row), axis=1)]
        return df

    def _detect_encoding(self, path: Path) -> str:
        for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                with open(path, encoding=encoding) as f:
                    f.read(4096)
                return encoding
            except (UnicodeDecodeError, UnicodeError):
                continue
        return "utf-8"

    def _detect_delimiter(self, path: Path, encoding: str) -> str:
        with open(path, encoding=encoding) as f:
            sample = f.read(4096)
        candidates = {",": 0, "\t": 0, ";": 0, "|": 0}
        for line in sample.split("\n")[:5]:
            for d in candidates:
                candidates[d] += line.count(d)
        best = max(candidates, key=lambda k: candidates[k])
        return best if candidates[best] > 0 else ","
