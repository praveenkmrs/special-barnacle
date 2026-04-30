from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path

from core.parsing.raw_transaction import RawTransaction


class BankAdapter(ABC):
    bank_code: str
    display_name: str
    supported_formats: list[str]

    @abstractmethod
    def detect(self, file_path: Path) -> bool:
        """Return True if this adapter recognizes the file."""

    @abstractmethod
    def parse(
        self,
        file_path: Path,
        password: str | None = None,
        *,
        account_id: int,
    ) -> list[RawTransaction]:
        """Parse statement file → list of normalized RawTransaction."""

    @abstractmethod
    def statement_period(
        self, file_path: Path, password: str | None = None
    ) -> tuple[date, date]:
        """Return (start_date, end_date) covered by this statement."""
