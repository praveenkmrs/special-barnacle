from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BankConfig:
    bank_code: str
    bank_name: str
    account_type: str

    columns: dict[str, str] = field(default_factory=dict)

    date_format: str = "%d/%m/%y"
    date_format_alt: str | None = None

    currency: str = "INR"

    multiline_narration: bool = False
    narration_merge_strategy: str = "concat_until_next_date"

    detection_patterns: list[str] = field(default_factory=list)
    header_patterns: list[str] = field(default_factory=list)

    csv_delimiter: str = ","
    csv_encoding: str = "utf-8"
    csv_skip_header_rows: int = 0
    csv_skip_footer_rows: int = 0

    password_hint: str = ""
