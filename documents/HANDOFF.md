# HDFC Parser — Implementation Handoff (v1-aligned)

> **This document is the implementation reference for the HDFC bank adapter inside the FinAssist v1 application.**
>
> It is a **companion** to `finassist-v1-plan.md`, not a replacement. Where this document and the v1 plan disagree on schema, project structure, categories, or build phasing, **the v1 plan wins**. This document only covers HDFC parser internals.
>
> Read the v1 plan first. Read this second.

---

## 0. Scope of This Document

**Covers:**
- HDFC Bank statement format specification (PDF and CSV)
- The internal implementation of `core/banks/hdfc/` package
- Shared parsing utilities in `core/parsing/` (Indian amount parser, date parser, UPI parser, decryptor, multi-line merger, dedup hashing)
- The public `HDFCAdapter` class that satisfies the `BankAdapter` interface defined in the v1 plan

**Does NOT cover** (see v1 plan):
- Full project structure / Docker / FastAPI / React layer
- SQLite schema for `transactions`, `accounts`, `categories`, `rules`, `subscriptions`, `holdings`, etc.
- Category taxonomy
- Classification engine (Tier 1/2/3)
- Cash envelopes, subscriptions, investments, transfer detection
- Build phases (the v1 plan has its own 9-phase sequence)

**Out of v1 scope entirely** (preserved as appendix only):
- SBI and Axis adapters — see §22

---

## 1. How This Fits With the v1 Plan

```
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI route                           │
│              POST /imports  (file + account_id)                 │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│         core.banks.registry.detect_bank(file_path)              │
│         returns HDFCAdapter() if HDFC patterns found            │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                 HDFCAdapter.parse(file, password)               │
│                                                                 │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────────┐    │
│  │ PDF route   │ OR │ CSV route    │    │ XLSX (deferred)  │    │
│  └──────┬──────┘    └──────┬───────┘    └──────────────────┘    │
│         │                  │                                    │
│         ▼                  ▼                                    │
│  ┌─────────────┐    ┌──────────────┐                            │
│  │ pikepdf     │    │ pandas       │                            │
│  │ decrypt     │    │ read_csv     │                            │
│  └──────┬──────┘    └──────┬───────┘                            │
│         │                  │                                    │
│         ▼                  │                                    │
│  ┌─────────────┐           │                                    │
│  │ pdfplumber  │           │                                    │
│  │ extract     │           │                                    │
│  └──────┬──────┘           │                                    │
│         │                  │                                    │
│         ▼                  │                                    │
│  ┌─────────────────────┐   │                                    │
│  │ multiline merger    │   │                                    │
│  │ (HDFC PDF only)     │   │                                    │
│  └──────┬──────────────┘   │                                    │
│         │                  │                                    │
│         └────────┬─────────┘                                    │
│                  ▼                                              │
│         ┌────────────────────┐                                  │
│         │ normalize_to_raw   │                                  │
│         │ (col map + amount/ │                                  │
│         │  date parsers +    │                                  │
│         │  narration clean + │                                  │
│         │  hash)             │                                  │
│         └────────┬───────────┘                                  │
│                  │                                              │
│                  ▼                                              │
│         list[RawTransaction]                                    │
└──────────────────┬──────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│             Persistence layer (api/routes/imports.py)           │
│     RawTransaction → transactions table row                     │
│     Composite UNIQUE rejects duplicates                         │
│     classification_source = 'unclassified' (Tier1/2/3 runs next)│
└─────────────────────────────────────────────────────────────────┘
```

The parser's **only** output is `list[RawTransaction]`. Everything downstream — classification, transfer detection, subscription linking — is in other modules per the v1 plan.

---

## 2. HDFC Statement Format Specification

### 2.1 PDF Format (most common)

**PDF table columns (left to right):**
```
Date | Narration | Chq./Ref.No. | Value Dt | Withdrawal Amt. | Deposit Amt. | Closing Balance
```

| Field | Notes |
|---|---|
| Date | `DD/MM/YY` (e.g., `22/06/17`) — sometimes `DD/MM/YYYY`. Years 00-29 → 2000-2029. |
| Narration | **Multi-line.** A single transaction's description spans 2-3 PDF rows. Continuation rows have empty Date column. Must be merged BEFORE column normalization. |
| Chq./Ref.No. | Optional reference (cheque/transaction reference) |
| Value Dt | Value date (often same as Date) |
| Withdrawal Amt. | Debit amount, Indian comma format (`1,00,000.00`); empty for credits |
| Deposit Amt. | Credit amount, Indian comma format; empty for debits |
| Closing Balance | Running balance after this transaction |

**Encryption:**
- Email PDFs: encrypted; password is **9-digit Customer ID**.
- NetBanking-downloaded PDFs: usually NOT password-protected.

**Detection patterns** (text substrings to look for in extracted text):
- `"HDFC BANK"`
- `"Statement of account"`
- `"Withdrawal Amt."`
- `"Narration"`

### 2.2 CSV Format (when available)

Same column structure as PDF table. Headers may have trailing spaces. Tab or comma delimiter (auto-detect required). No multi-line narration issue.

### 2.3 Narration Sub-Patterns

UPI/IMPS/NEFT/RTGS narrations are semi-structured. The UPI sub-parser extracts these.

- **UPI:** `UPI-<MASKED_ACCT>-<IFSC>-<REF>-` — example: `UPI-XXXXXX0315-ICIC0007236-128994831651-`
- **IMPS:** `IMPS-<REF>-<NAME>-<IFSC>` — example: `IMPS-128713626494-NEXTBILLION TECHNOLO-Y`
- **NEFT:** `NEFT-<REF>-<NAME>-<IFSC>-...`
- **RTGS:** `RTGS-<REF>-...`
- **ATM:** prefix `ATW` or `NWD` — example: `ATW-XXXXXXXX-NS<location>`
- **Cash withdrawal at branch:** `CASH WDL...`
- **Salary credit:** typically `NEFT-<EMP_ID>-...-SAL` or `ACH C-<COMPANY>-...`
- **SIP debit:** `ACH D-<AMC>-<FOLIO>-...` (e.g., `ACH D- HDFC AMC- LIQUIDITY...`)
- **Reversals:** narration contains `REVERSAL` or `REF` token; appears as positive credit

### 2.4 Edge Cases (must be handled)

- **Multi-line narration** (the big one — see §10)
- **Indian number formatting** — `,` is both thousand and lakh separator; standard parsers fail. See §6.
- **Date format ambiguity** — `01/02/24` is `1-Feb-2024` in HDFC, never `Feb-1`. Always use `dayfirst=True`.
- **Empty Withdrawal AND Deposit** — opening balance row or summary row; skip.
- **Both Withdrawal AND Deposit populated** — should not happen; net them and pick larger direction (defensive).
- **`nan` artifacts** — pdfplumber sometimes emits `nan` in empty cells; clean these.
- **Trailing whitespace in column headers** — strip on read.
- **Salary credit narrations vary monthly** — employer payroll IDs change; classifier handles, not parser.

---

## 3. Module Layout (HDFC parser layer only)

```
core/
├── banks/
│   ├── base.py                    # BankAdapter ABC (defined in v1 plan §3)
│   ├── registry.py                # ADAPTERS list + detect_bank()
│   └── hdfc/
│       ├── __init__.py            # exports HDFCAdapter
│       ├── adapter.py             # HDFCAdapter class
│       ├── config.py              # HDFC_SAVINGS BankConfig dataclass
│       ├── pdf_parser.py          # HDFC PDF extraction (pdfplumber)
│       ├── csv_parser.py          # HDFC CSV extraction (pandas)
│       └── multiline_merger.py    # HDFC-specific multi-line merge
└── parsing/                       # SHARED parsing utilities (bank-agnostic)
    ├── raw_transaction.py         # RawTransaction dataclass
    ├── bank_config.py             # BankConfig dataclass (internal config helper)
    ├── amount_parser.py           # Indian number format
    ├── date_parser.py             # multi-format date + looks_like_date()
    ├── upi_parser.py              # UPI/IMPS/NEFT narration extraction
    ├── decryptor.py               # pikepdf wrapper
    ├── normalizer.py              # raw DataFrame → list[RawTransaction]
    ├── narration_clean.py         # whitespace, nan removal, hashing
    └── balance_validator.py       # running balance chain check
```

**Note:** the multi-line merger lives under `hdfc/` initially. When Axis is added later (also multi-line), this can be lifted to `core/parsing/multiline_merger.py` — the strategy is already config-driven.

---

## 4. Dependencies

```
# Core PDF parsing
pdfplumber>=0.11.0          # Primary PDF table extraction
pikepdf>=9.0                # PDF decryption
PyMuPDF>=1.24               # Fast text extraction fallback (import fitz)

# Data handling
pandas>=2.2                 # CSV parsing + DataFrame ops
openpyxl>=3.1               # .xlsx support (for future)

# File detection
python-magic>=0.4.27        # Magic-byte file type detection

# Date handling
python-dateutil>=2.9        # Flexible multi-format date fallback

# OCR (deferred — not in v1 scope)
# pytesseract>=0.3.13
# Pillow>=10.0
```

**Dockerfile system packages:**
```dockerfile
RUN apt-get update && apt-get install -y \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*
```

Python: **3.14.4** (per v1 plan).

---

## 5. RawTransaction (intermediate dataclass)

The parser produces `RawTransaction` objects. The persistence layer maps these to rows in the v1 plan's `transactions` table. Classification fields are NOT set here — they default to `unclassified` in the persistence layer.

```python
# core/parsing/raw_transaction.py

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional, Literal
import hashlib
import re


TxnType = Literal["debit", "credit"]


@dataclass
class RawTransaction:
    """
    Output of the parser layer. Bank-agnostic intermediate representation.
    Mapped to the `transactions` table by the persistence layer.
    """

    # Core
    txn_date: date
    amount: Decimal                    # Always positive
    type: TxnType                      # 'debit' or 'credit'
    narration: str                     # Cleaned
    balance_after: Optional[Decimal]

    # Linkage
    account_id: int                    # FK to accounts.id (set by caller)
    bank_code: str = "HDFC"

    # Optional reference fields
    reference: Optional[str] = None
    value_date: Optional[date] = None

    # Source provenance
    source_file: str = ""
    source_page: Optional[int] = None
    source_line: Optional[int] = None

    # Raw preservation (for re-parsing if logic improves)
    raw_narration: str = ""
    raw_date_str: str = ""
    raw_amount_str: str = ""

    # Computed dedup hash (SHA-256 of normalized narration)
    narration_hash: str = ""

    # Currency (always INR in v1)
    currency: str = "INR"

    def compute_hash(self) -> str:
        """
        Hash the normalized narration only.
        Dedup decisions live in the import service (v1 plan §11.5), which combines
        this hash with reference and balance_after to classify each incoming
        transaction as clean / definite-duplicate / ambiguous-needs-review.
        The hash itself only needs to fingerprint the narration.
        """
        normalized = _normalize_for_hash(self.narration)
        self.narration_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return self.narration_hash


def _normalize_for_hash(narration: str) -> str:
    """Normalize narration before hashing: lowercase, collapse whitespace."""
    if not narration:
        return ""
    s = narration.lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s
```

---

## 6. Indian Amount Parser

Indian number formatting uses lakh/crore grouping: `1,00,000.00` for one lakh.

```python
# core/parsing/amount_parser.py

from decimal import Decimal, InvalidOperation
from typing import Optional
import re


def parse_indian_amount(amount_str: Optional[str]) -> Decimal:
    """
    Parse Indian-formatted currency amounts.

    Handles:
    - "1,00,000.00" → Decimal("100000.00") (lakh grouping)
    - "1,00,00,000.00" → Decimal("10000000.00") (crore grouping)
    - "50,000.00" → Decimal("50000.00")
    - "0.50" → Decimal("0.50")
    - "" / None / "-" / "nan" / "—" / "–" → Decimal("0.00")
    - "(1,500.00)" → Decimal("-1500.00") (parentheses negative)
    - "1,500.00Dr" → Decimal("-1500.00")
    - "1,500.00Cr" → Decimal("1500.00")
    - "₹1,500.00" / "Rs. 1,500" / "INR 1500" → Decimal("1500.00")

    Returns Decimal for precision. Never returns float.
    """
    if not amount_str:
        return Decimal("0.00")

    cleaned = str(amount_str).strip()

    if cleaned in ("", "-", "nan", "None", "null", "—", "–"):
        return Decimal("0.00")

    # Parentheses negative: (1,500.00) → -1500.00
    is_negative = False
    if cleaned.startswith("(") and cleaned.endswith(")"):
        is_negative = True
        cleaned = cleaned[1:-1].strip()

    # Explicit negative sign
    if cleaned.startswith("-"):
        is_negative = True
        cleaned = cleaned[1:].strip()

    # Dr/Cr suffixes
    if cleaned.upper().endswith("DR"):
        is_negative = True
        cleaned = cleaned[:-2].strip()
    elif cleaned.upper().endswith("CR"):
        cleaned = cleaned[:-2].strip()

    # Currency symbols
    cleaned = re.sub(r"^(₹|Rs\.?|INR)\s*", "", cleaned).strip()

    # Drop ALL commas (handles both Indian and Western grouping)
    cleaned = cleaned.replace(",", "").replace(" ", "")

    if not cleaned:
        return Decimal("0.00")

    try:
        result = Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"Cannot parse amount: '{amount_str}' (cleaned: '{cleaned}')")

    return -result if is_negative else result
```

### Test cases (must pass)

```
test_parse_lakh: "1,00,000.00" → Decimal("100000.00")
test_parse_crore: "1,00,00,000.00" → Decimal("10000000.00")
test_parse_simple: "500.00" → Decimal("500.00")
test_parse_paisa: "0.50" → Decimal("0.50")
test_parse_empty: "" → Decimal("0.00")
test_parse_dash: "-" → Decimal("0.00")
test_parse_emdash: "—" → Decimal("0.00")
test_parse_nan: "nan" → Decimal("0.00")
test_parse_currency_symbol: "₹1,500.00" → Decimal("1500.00")
test_parse_rs_prefix: "Rs. 1,500" → Decimal("1500.00")
test_parse_inr_prefix: "INR 1500" → Decimal("1500.00")
test_parse_parentheses_negative: "(1,500.00)" → Decimal("-1500.00")
test_parse_dr_suffix: "1,500.00Dr" → Decimal("-1500.00")
test_parse_cr_suffix: "1,500.00Cr" → Decimal("1500.00")
test_parse_explicit_negative: "-1500" → Decimal("-1500")
test_parse_with_spaces: " 1,500.00 " → Decimal("1500.00")
test_parse_invalid_raises: "abc" → raises ValueError
```

---

## 7. Multi-Format Date Parser

```python
# core/parsing/date_parser.py

from datetime import date, datetime
from typing import Optional
from dateutil import parser as dateutil_parser
import re


# Bank-specific formats — tried in order
KNOWN_FORMATS = [
    "%d/%m/%y",         # 22/06/17 (HDFC)
    "%d/%m/%Y",         # 22/06/2017 (HDFC alt)
    "%d %b %Y",         # 2 Jan 2013
    "%d-%m-%Y",         # 15-06-2024
    "%d-%b-%Y",         # 15-Jun-2024
    "%d %b %y",         # 2 Jan 13
    "%Y-%m-%d",         # ISO 8601
]


def parse_date(
    date_str: Optional[str],
    primary_format: Optional[str] = None,
    fallback_format: Optional[str] = None,
) -> Optional[date]:
    """
    Parse a date string with bank-specific format and fallbacks.

    Order:
    1. primary_format (from BankConfig)
    2. fallback_format (from BankConfig)
    3. KNOWN_FORMATS in order
    4. dateutil fuzzy parser (dayfirst=True) as last resort

    Returns None if unparseable.
    """
    if not date_str:
        return None

    cleaned = str(date_str).strip()
    if cleaned in ("", "nan", "None", "-"):
        return None

    cleaned = re.sub(r"\s+", " ", cleaned)

    formats_to_try: list[str] = []
    if primary_format:
        formats_to_try.append(primary_format)
    if fallback_format:
        formats_to_try.append(fallback_format)
    formats_to_try.extend(KNOWN_FORMATS)

    seen: set[str] = set()
    unique_formats: list[str] = []
    for fmt in formats_to_try:
        if fmt not in seen:
            seen.add(fmt)
            unique_formats.append(fmt)

    for fmt in unique_formats:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue

    # Last resort: dateutil — always dayfirst=True for Indian context
    try:
        return dateutil_parser.parse(cleaned, dayfirst=True).date()
    except (ValueError, TypeError):
        return None


def looks_like_date(value: str) -> bool:
    """
    Quick heuristic — does this string LOOK like a date?
    Used by multi-line merger to decide if a row starts a new transaction
    or continues the previous one. Pattern-only; no full parsing for speed.
    """
    if not value:
        return False
    cleaned = str(value).strip()
    if not cleaned or cleaned in ("nan", "None", "-", ""):
        return False
    # Starts with 1-2 digits then a date separator (slash, hyphen, space)
    return bool(re.match(r"^\d{1,2}[\s/\-]", cleaned))
```

### Test cases

```
test_hdfc_short_year: "22/06/17" → date(2017, 6, 22)
test_hdfc_full_year: "22/06/2017" → date(2017, 6, 22)
test_axis_format: "15-06-2024" → date(2024, 6, 15)
test_iso_format: "2024-06-15" → date(2024, 6, 15)
test_empty: "" → None
test_nan: "nan" → None
test_dayfirst_ambiguous: "01/02/24" → date(2024, 2, 1)   # Indian convention
test_invalid: "not a date" → None
test_looks_like_date_positive: "22/06/17" → True
test_looks_like_date_negative: "IMPS TRANSFER" → False
test_looks_like_date_empty: "" → False
```

---

## 8. UPI Narration Parser

Extracts structured fields from UPI/IMPS/NEFT/RTGS narrations. Used by the classifier later to generate VPA/merchant patterns.

```python
# core/parsing/upi_parser.py

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class UPIDetails:
    method: str = "UPI"                      # UPI / IMPS / NEFT / RTGS
    counterparty_name: Optional[str] = None
    counterparty_vpa: Optional[str] = None
    counterparty_ifsc: Optional[str] = None
    reference_number: Optional[str] = None
    remark: Optional[str] = None


_IFSC_RE = re.compile(r"^[A-Z]{4}[0-9A-Z]{7}$")
_REF_RE = re.compile(r"^\d{8,18}$")


def parse_upi_narration(narration: str) -> Optional[UPIDetails]:
    """
    Parse UPI/IMPS/NEFT/RTGS narration into structured fields.

    HDFC patterns (hyphen-delimited):
        UPI-XXXXXX0315-ICIC0007236-128994831651-
        IMPS-128713626494-NEXTBILLION TECHNOLO-Y
        NEFT-<REF>-<NAME>-<IFSC>-...

    Returns None if narration doesn't start with a known method.
    """
    if not narration:
        return None

    narration = str(narration).strip()
    upper = narration.upper()

    method: Optional[str] = None
    for m in ("UPI", "IMPS", "NEFT", "RTGS"):
        if upper.startswith(m):
            method = m
            break
    if not method:
        return None

    details = UPIDetails(method=method)

    # HDFC hyphen-delimited
    if "-" in narration and "/" not in narration:
        parts = [p.strip() for p in narration.split("-") if p.strip()]
        # parts[0] = method
        for part in parts[1:]:
            if _IFSC_RE.match(part):
                details.counterparty_ifsc = part
            elif _REF_RE.match(part):
                details.reference_number = part
            elif "@" in part:
                details.counterparty_vpa = part
            elif len(part) > 2 and not part.startswith("X"):
                # First non-masked text token = likely name
                if not details.counterparty_name:
                    details.counterparty_name = part

    # Slash-delimited (e.g., legacy SBI patterns — kept for forward-compat)
    elif "/" in narration:
        parts = [p.strip() for p in narration.split("/") if p.strip()]
        if len(parts) >= 4:
            details.reference_number = parts[2] if len(parts) > 2 else None
            details.counterparty_name = parts[3] if len(parts) > 3 else None
            if len(parts) > 4 and _IFSC_RE.match(parts[4]):
                details.counterparty_ifsc = parts[4]

    return details
```

### Test cases

```
test_upi_hdfc: "UPI-XXXXXX0315-ICIC0007236-128994831651-"
  → method=UPI, ifsc=ICIC0007236, ref=128994831651
test_imps_hdfc: "IMPS-128713626494-NEXTBILLION TECHNOLO-Y"
  → method=IMPS, ref=128713626494, name=NEXTBILLION TECHNOLO
test_vpa_present: "UPI-johndoe@okicici-..."
  → vpa=johndoe@okicici
test_non_payment: "ATM WDL-..." → None
test_empty: "" → None
```

---

## 9. PDF Decryptor

```python
# core/parsing/decryptor.py

from pathlib import Path
from typing import Optional
import tempfile
import pikepdf


class PDFPasswordRequired(Exception):
    """Raised when an encrypted PDF needs a password."""


class PDFPasswordIncorrect(Exception):
    """Raised when the supplied password is wrong."""


def decrypt_pdf(pdf_path: Path, password: Optional[str] = None) -> Path:
    """
    Decrypt a password-protected PDF.

    - If not encrypted: returns the original path.
    - If encrypted + correct password: writes decrypted copy to a temp file, returns that path.
    - If encrypted + no password: raises PDFPasswordRequired.
    - If encrypted + wrong password: raises PDFPasswordIncorrect.

    Caller is responsible for cleaning up the temp directory if returned path differs from input.
    """
    # Try opening without password — succeeds if not encrypted
    try:
        with pikepdf.open(str(pdf_path)) as _:
            return pdf_path
    except pikepdf.PasswordError:
        pass

    if not password:
        raise PDFPasswordRequired(
            f"PDF '{pdf_path.name}' is password-protected. "
            f"For HDFC: use your 9-digit Customer ID."
        )

    try:
        with pikepdf.open(str(pdf_path), password=password) as pdf:
            temp_dir = Path(tempfile.mkdtemp(prefix="finassist_"))
            decrypted = temp_dir / f"decrypted_{pdf_path.name}"
            pdf.save(str(decrypted))
            return decrypted
    except pikepdf.PasswordError as e:
        raise PDFPasswordIncorrect(
            f"Incorrect password for '{pdf_path.name}'."
        ) from e
```

---

## 10. Multi-line Narration Merger (THE critical HDFC fix)

This is the single most important parsing routine. HDFC PDFs split a transaction's narration across 2-3 PDF table rows. Continuation rows have an empty Date column.

**Strategy: `concat_until_next_date`**
- A row whose Date column matches `looks_like_date()` → starts a new transaction.
- A row whose Date column is empty/non-date → continuation of the previous transaction; append its narration text to the parent row's narration.

**This must run BEFORE column normalization, on the raw DataFrame with the bank's original column headers.**

```python
# core/banks/hdfc/multiline_merger.py

import pandas as pd
from core.parsing.date_parser import looks_like_date
from core.parsing.bank_config import BankConfig


def merge_multiline_narrations(df: pd.DataFrame, config: BankConfig) -> pd.DataFrame:
    """
    Merge HDFC's multi-line narrations into single rows.

    Pre-condition: df contains raw bank columns including the Date and Narration columns.
    Post-condition: each row corresponds to one logical transaction with a complete narration.
    """
    if not config.multiline_narration:
        return df

    date_col = config.columns.get("date", "")
    narration_col = config.columns.get("narration", "")
    if not date_col or not narration_col:
        return df

    # Case-insensitive match if exact column not found
    if date_col not in df.columns or narration_col not in df.columns:
        for col in df.columns:
            if col.strip().lower() == date_col.strip().lower():
                date_col = col
            if col.strip().lower() == narration_col.strip().lower():
                narration_col = col

    merged_rows: list[pd.Series] = []
    current: pd.Series | None = None

    for _, row in df.iterrows():
        date_value = str(row.get(date_col, "")).strip()

        if looks_like_date(date_value):
            # New transaction
            if current is not None:
                merged_rows.append(current)
            current = row.copy()
        else:
            # Continuation line — append narration to current
            if current is not None:
                continuation = str(row.get(narration_col, "")).strip()
                if continuation and continuation.lower() != "nan":
                    existing = str(current[narration_col]).strip()
                    current[narration_col] = f"{existing} {continuation}".strip()
            # else: orphan continuation before any transaction → skip

    if current is not None:
        merged_rows.append(current)

    return pd.DataFrame(merged_rows).reset_index(drop=True)
```

### Test cases

```
test_hdfc_multiline: 5 raw rows (3 with dates, 2 continuations) → 3 merged transactions
test_no_multiline: all rows have dates → no merging, output == input
test_three_line_narration: date row + 2 continuation rows → 1 transaction with 3 parts joined
test_orphan_continuation: continuation row with no preceding date row → skipped
test_empty_continuation: continuation row with empty narration → no append, no error
test_nan_continuation: continuation cell is "nan" → skipped (treated as empty)
```

---

## 11. BankConfig (internal helper)

This is an INTERNAL config dataclass used by HDFC's parser components. The PUBLIC contract that the rest of the app consumes is `BankAdapter` (defined in v1 plan §3). Adapter wraps the config.

```python
# core/parsing/bank_config.py

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BankConfig:
    """Internal parser config for one bank+account-type combination."""

    bank_code: str                         # "HDFC"
    bank_name: str                         # "HDFC Bank"
    account_type: str                      # "savings"

    # Map canonical fields → bank's column header text
    # Keys: "date", "narration", "reference", "value_date", "debit", "credit", "balance"
    columns: dict[str, str] = field(default_factory=dict)

    # Date parsing
    date_format: str = "%d/%m/%y"
    date_format_alt: Optional[str] = None

    # Amount parsing
    currency: str = "INR"

    # Multi-line narration
    multiline_narration: bool = False
    narration_merge_strategy: str = "concat_until_next_date"

    # Detection (for content-based bank identification)
    detection_patterns: list[str] = field(default_factory=list)

    # Header row detection
    header_patterns: list[str] = field(default_factory=list)

    # CSV-specific
    csv_delimiter: str = ","
    csv_encoding: str = "utf-8"
    csv_skip_header_rows: int = 0
    csv_skip_footer_rows: int = 0

    # Password hint shown to the user in the UI
    password_hint: str = ""
```

### HDFC config

```python
# core/banks/hdfc/config.py

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
```

---

## 12. CSV Parser (HDFC)

```python
# core/banks/hdfc/csv_parser.py

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

        # Strip whitespace from headers
        df.columns = [c.strip() for c in df.columns]

        # Drop fully-empty rows
        df = df.dropna(how="all")
        df = df[~df.apply(lambda row: all(str(v).strip() == "" for v in row), axis=1)]

        return df

    def _detect_encoding(self, path: Path) -> str:
        for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                with open(path, "r", encoding=encoding) as f:
                    f.read(4096)
                return encoding
            except (UnicodeDecodeError, UnicodeError):
                continue
        return "utf-8"

    def _detect_delimiter(self, path: Path, encoding: str) -> str:
        with open(path, "r", encoding=encoding) as f:
            sample = f.read(4096)

        candidates = {",": 0, "\t": 0, ";": 0, "|": 0}
        for line in sample.split("\n")[:5]:
            for d in candidates:
                candidates[d] += line.count(d)

        best = max(candidates, key=candidates.get)
        return best if candidates[best] > 0 else ","
```

---

## 13. PDF Parser (HDFC, pdfplumber)

```python
# core/banks/hdfc/pdf_parser.py

from pathlib import Path
import pandas as pd
import pdfplumber

from core.parsing.bank_config import BankConfig


class HDFCPDFParser:
    """Text-based PDF parser. NOT for scanned PDFs (OCR deferred)."""

    def __init__(self, config: BankConfig):
        self.config = config

    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".pdf"

    def extract_raw(self, pdf_path: Path) -> pd.DataFrame:
        """Caller must pass a decrypted PDF path."""
        if not self._is_text_based(pdf_path):
            raise ValueError(
                f"PDF appears scanned/image-based. OCR not supported in v1: {pdf_path}"
            )

        all_rows: list[list[str]] = []
        header: list[str] | None = None

        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables(table_settings={
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 5,
                    "join_tolerance": 5,
                    "edge_min_length": 10,
                    "min_words_vertical": 2,
                    "min_words_horizontal": 1,
                })

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
        match_count = sum(
            1 for p in self.config.header_patterns if p.lower() in text
        )
        return match_count >= 2
```

---

## 14. Normalizer (raw DataFrame → list[RawTransaction])

Bank-agnostic — works for any bank with a populated `BankConfig`.

```python
# core/parsing/normalizer.py

from decimal import Decimal
import re
import pandas as pd

from core.parsing.raw_transaction import RawTransaction
from core.parsing.bank_config import BankConfig
from core.parsing.amount_parser import parse_indian_amount
from core.parsing.date_parser import parse_date


def normalize_dataframe(
    df: pd.DataFrame,
    config: BankConfig,
    *,
    account_id: int,
    source_file: str = "",
) -> tuple[list[RawTransaction], list[dict]]:
    """
    Convert a raw bank DataFrame into RawTransaction objects.

    Returns: (transactions, skipped_rows)
    `skipped_rows` is a list of {index, reason, raw_row} for diagnostics.
    """
    transactions: list[RawTransaction] = []
    skipped: list[dict] = []

    col_map = config.columns

    for idx, row in df.iterrows():
        try:
            # Date
            raw_date_str = str(row.get(col_map.get("date", ""), "")).strip()
            txn_date = parse_date(
                raw_date_str,
                primary_format=config.date_format,
                fallback_format=config.date_format_alt,
            )
            if txn_date is None:
                skipped.append({"index": idx, "reason": "unparseable date", "raw": dict(row)})
                continue

            # Value date (optional)
            value_date = None
            vd_col = col_map.get("value_date", "")
            if vd_col and vd_col in df.columns:
                vd_str = str(row.get(vd_col, "")).strip()
                value_date = parse_date(vd_str, config.date_format, config.date_format_alt)

            # Amounts
            debit_str = str(row.get(col_map.get("debit", ""), "")).strip()
            credit_str = str(row.get(col_map.get("credit", ""), "")).strip()
            balance_str = str(row.get(col_map.get("balance", ""), "")).strip()

            debit_amt = parse_indian_amount(debit_str)
            credit_amt = parse_indian_amount(credit_str)
            balance = parse_indian_amount(balance_str) if balance_str else None

            # Direction
            if debit_amt > 0 and credit_amt == 0:
                txn_type, amount = "debit", debit_amt
                raw_amount_str = debit_str
            elif credit_amt > 0 and debit_amt == 0:
                txn_type, amount = "credit", credit_amt
                raw_amount_str = credit_str
            elif debit_amt > 0 and credit_amt > 0:
                # Defensive: both populated → net them
                if debit_amt > credit_amt:
                    txn_type, amount = "debit", debit_amt - credit_amt
                else:
                    txn_type, amount = "credit", credit_amt - debit_amt
                raw_amount_str = f"D:{debit_str}|C:{credit_str}"
            else:
                # Both zero — opening balance / summary row
                skipped.append({"index": idx, "reason": "zero amount row", "raw": dict(row)})
                continue

            # Narration
            raw_narration = str(row.get(col_map.get("narration", ""), "")).strip()
            narration = _clean_narration(raw_narration)

            # Reference
            reference = None
            ref_col = col_map.get("reference", "")
            if ref_col and ref_col in df.columns:
                ref = str(row.get(ref_col, "")).strip()
                if ref and ref.lower() != "nan":
                    reference = ref

            # Source page
            source_page = None
            if "_source_page" in df.columns:
                try:
                    source_page = int(row["_source_page"])
                except (ValueError, TypeError):
                    pass

            txn = RawTransaction(
                txn_date=txn_date,
                amount=amount,
                type=txn_type,
                narration=narration,
                balance_after=balance if balance is not None and balance != Decimal("0.00") else None,
                account_id=account_id,
                bank_code=config.bank_code,
                reference=reference,
                value_date=value_date,
                source_file=source_file,
                source_page=source_page,
                source_line=int(idx) + 1,
                raw_narration=raw_narration,
                raw_date_str=raw_date_str,
                raw_amount_str=raw_amount_str,
                currency=config.currency,
            )
            txn.compute_hash()
            transactions.append(txn)

        except Exception as e:
            skipped.append({"index": idx, "reason": f"exception: {e}", "raw": dict(row)})

    return transactions, skipped


def _clean_narration(narration: str) -> str:
    if not narration or narration.lower() == "nan":
        return ""
    cleaned = re.sub(r"\s+", " ", narration).strip()
    # Strip stray 'nan' fragments from PDF multi-line merging artifacts
    cleaned = re.sub(r"\bnan\b", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned
```

---

## 15. Bank Detection (HDFC-only registry in v1)

```python
# core/banks/registry.py

from pathlib import Path
from typing import Optional
import pdfplumber

from core.banks.base import BankAdapter
from core.banks.hdfc.adapter import HDFCAdapter


ADAPTERS: list[BankAdapter] = [HDFCAdapter()]


def detect_bank(file_path: Path) -> Optional[BankAdapter]:
    """Return the first adapter whose detect() returns True."""
    for adapter in ADAPTERS:
        try:
            if adapter.detect(file_path):
                return adapter
        except Exception:
            continue
    return None


def _extract_sample_text(file_path: Path) -> str:
    """Helper for adapters: pull a snippet of text from PDF/CSV for pattern matching."""
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        try:
            with pdfplumber.open(str(file_path)) as pdf:
                text = ""
                for page in pdf.pages[:2]:
                    text += (page.extract_text() or "") + "\n"
                return text
        except Exception:
            return ""

    elif suffix in (".csv", ".tsv", ".txt"):
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return "".join(f.readline() for _ in range(20))
        except Exception:
            return ""

    elif suffix in (".xls", ".xlsx"):
        try:
            import pandas as pd
            df = pd.read_excel(file_path, nrows=5, dtype=str)
            return " ".join(df.columns) + " " + df.to_string()
        except Exception:
            return ""

    return ""
```

---

## 16. HDFCAdapter (the public class — wires everything together)

```python
# core/banks/hdfc/adapter.py

from datetime import date
from pathlib import Path
from typing import Optional

from core.banks.base import BankAdapter
from core.banks.registry import _extract_sample_text
from core.banks.hdfc.config import HDFC_SAVINGS
from core.banks.hdfc.pdf_parser import HDFCPDFParser
from core.banks.hdfc.csv_parser import HDFCCSVParser
from core.banks.hdfc.multiline_merger import merge_multiline_narrations
from core.parsing.decryptor import decrypt_pdf
from core.parsing.normalizer import normalize_dataframe
from core.parsing.raw_transaction import RawTransaction


class HDFCAdapter(BankAdapter):
    bank_code = "HDFC"
    display_name = "HDFC Bank"
    supported_formats = ["pdf", "csv"]

    def __init__(self):
        self.config = HDFC_SAVINGS
        self.pdf_parser = HDFCPDFParser(self.config)
        self.csv_parser = HDFCCSVParser(self.config)

    def detect(self, file_path: Path) -> bool:
        text = _extract_sample_text(file_path).lower()
        if not text:
            return False
        match_count = sum(
            1 for pattern in self.config.detection_patterns
            if pattern.lower() in text
        )
        return match_count >= 2

    def parse(
        self,
        file_path: Path,
        password: Optional[str] = None,
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
            df_merged = df_raw  # CSVs do not have multi-line narration issue
        else:
            raise ValueError(f"HDFCAdapter does not support {suffix}")

        transactions, _skipped = normalize_dataframe(
            df_merged,
            self.config,
            account_id=account_id,
            source_file=file_path.name,
        )
        # Skipped rows are returned via a side channel in the route handler;
        # this method only returns successful transactions.
        return transactions

    def statement_period(self, file_path: Path) -> tuple[date, date]:
        """Return (min_date, max_date) across all transactions in the file."""
        # Placeholder: re-parses the file. Optimize later if needed.
        # For password-protected PDFs the route handler must supply the password.
        txns = self.parse(file_path, account_id=0)
        if not txns:
            raise ValueError("No transactions found; cannot determine period.")
        dates = [t.txn_date for t in txns]
        return min(dates), max(dates)
```

> **Note on the `BankAdapter` ABC defined in v1 plan §3:** that signature was `parse(file_path, password)`. `account_id` must also be passed because every `RawTransaction` carries it. **Update the ABC** to include `account_id` as a keyword-only parameter when implementing Phase 2.

---

## 17. Balance Validator (diagnostic tool)

Used to flag statements where the running balance chain doesn't reconcile. Not a hard fail — surfaces discrepancies to the user.

```python
# core/parsing/balance_validator.py

from decimal import Decimal
from typing import Optional
from core.parsing.raw_transaction import RawTransaction


def validate_running_balance(
    transactions: list[RawTransaction],
    opening_balance: Optional[Decimal] = None,
    tolerance: Decimal = Decimal("0.02"),
) -> list[dict]:
    """
    Verify previous_balance ± amount == current_balance for each transaction
    that has balance_after populated.

    Returns: list of discrepancy dicts. Empty list = all balances reconcile.
    """
    discrepancies: list[dict] = []
    if not transactions:
        return discrepancies

    prev_balance = opening_balance

    for idx, txn in enumerate(transactions):
        if txn.balance_after is None:
            prev_balance = None  # break chain
            continue

        if prev_balance is not None:
            if txn.type == "debit":
                expected = prev_balance - txn.amount
            else:
                expected = prev_balance + txn.amount

            diff = abs(expected - txn.balance_after)
            if diff > tolerance:
                discrepancies.append({
                    "index": idx,
                    "expected_balance": expected,
                    "actual_balance": txn.balance_after,
                    "difference": diff,
                    "txn_date": txn.txn_date,
                    "narration": txn.narration[:60],
                    "amount": txn.amount,
                    "type": txn.type,
                })

        prev_balance = txn.balance_after

    return discrepancies
```

---

## 18. Persistence: RawTransaction → `transactions` table

The route handler is responsible for translating `RawTransaction` to a row in the v1 plan's `transactions` table. Mapping:

| `transactions` column | Source |
|---|---|
| `account_id` | `RawTransaction.account_id` |
| `txn_date` | `RawTransaction.txn_date` |
| `amount` | `str(RawTransaction.amount)` (Decimal → TEXT) |
| `type` | `RawTransaction.type` |
| `narration` | `RawTransaction.narration` |
| `narration_hash` | `RawTransaction.narration_hash` |
| `balance_after` | `str(RawTransaction.balance_after)` if not None |
| `category_id` | NULL (classifier sets this) |
| `subscription_id` | NULL |
| `transfer_pair_id` | NULL |
| `is_transfer` | 0 |
| `classification_source` | `'unclassified'` |
| `classification_confidence` | NULL |
| `needs_review` | 1 (so it surfaces until classified) |

**Dedup:** The route handler/import service runs the **3-tier duplicate detector** described in v1 plan §11.5. Do **not** rely on a `UNIQUE` constraint — it would silently drop the second of two genuine same-day same-amount same-merchant transactions, which is data loss.

The detector returns one of three verdicts per incoming `RawTransaction`:
- **CLEAN** → insert with `needs_review=1` (so classifier review picks it up) but no `dup_group_id`.
- **DEFINITE_DUPLICATE** → skip; increment `imports.rows_duplicate`.
- **AMBIGUOUS** → insert + assign a shared `dup_group_id` to both the new row and the existing match(es); set `review_reason='duplicate'` and `needs_review=1` on all rows in the group. The user resolves them via the review queue's "Possible duplicates" pane.

Disambiguation depends on `reference` and `balance_after`. **Always populate these fields when the source data has them** — they are what prevents legitimate rows from being silently merged.

### Schema fields the parser populates

The v1 plan's `transactions` table (as updated alongside §11.5) includes the following parser-populated fields. The route handler must persist them:

```
reference        -- key disambiguator for duplicate detection
value_date       -- when the bank distinguishes txn_date from value_date
source_file      -- original filename, for debugging
source_page      -- PDF page number (PDF only)
source_line      -- row index in source file
raw_narration    -- original narration before _clean_narration
raw_date_str     -- original date string before parse_date
raw_amount_str   -- original amount string before parse_indian_amount
```

All nullable. They cost nothing in storage and are invaluable when:
- A duplicate group needs human review (raw fields show what the parser saw vs cleaned).
- Parser logic is improved later — re-parse from `raw_*` without re-importing files.
- The duplicate detector falls back to `reference` to confirm/deny dup status.

> If Claude Code finds these columns missing during Phase 2 build, that's a v1 plan bug — flag it. The plan as of this revision has them.

---

## 19. Test Cases (parser layer only)

```
tests/test_parsing/
├── test_amount_parser.py        # see §6
├── test_date_parser.py          # see §7
├── test_upi_parser.py           # see §8
└── test_normalizer.py
    - test_hdfc_csv_normalization: synthetic HDFC CSV → list[RawTransaction]
    - test_direction_detection_debit
    - test_direction_detection_credit
    - test_zero_amount_row_skipped
    - test_unparseable_date_row_skipped
    - test_both_debit_and_credit_populated_handled
    - test_narration_cleaning: extra whitespace, 'nan' stripped
    - test_hash_stability: same narration → same hash
    - test_hash_differentiation: different narration → different hash

tests/test_banks/test_hdfc/
├── test_config.py
│   - test_detection_patterns_present
├── test_csv_parser.py
│   - test_can_handle_csv_tsv_txt
│   - test_extract_strips_header_whitespace
│   - test_extract_drops_empty_rows
│   - test_encoding_detection_utf8_bom
├── test_multiline_merger.py
│   - test_5_raw_rows_merge_to_3
│   - test_no_multiline_when_disabled
│   - test_three_line_narration
│   - test_orphan_continuation_dropped
├── test_pdf_parser.py
│   - test_text_based_pdf_extracted
│   - test_scanned_pdf_raises
│   - test_header_detection
└── test_adapter.py
    - test_detect_returns_true_for_hdfc_csv
    - test_detect_returns_false_for_unknown
    - test_parse_csv_end_to_end
    - test_parse_pdf_with_password
    - test_parse_pdf_wrong_password_raises

tests/test_parsing/test_balance_validator.py
    - test_valid_chain_no_discrepancies
    - test_one_off_balance_flagged
    - test_tolerance_applied
    - test_chain_break_on_null_balance
```

### Synthetic fixtures

Bank statements contain personal data — do NOT commit real ones. Generate synthetic fixtures in `tests/conftest.py`:

```python
import csv
import pytest
from pathlib import Path


@pytest.fixture
def hdfc_csv_simple(tmp_path) -> Path:
    """Minimal HDFC CSV with 4 transactions, single-line narrations."""
    file_path = tmp_path / "hdfc_simple.csv"
    rows = [
        ["Date", "Narration", "Chq./Ref.No.", "Value Dt",
         "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"],
        ["01/01/24", "UPI-JOHN DOE-OKICICI-12345-", "00001234", "01/01/24",
         "500.00", "", "49,500.00"],
        ["02/01/24", "NEFT-SALARY-COMPANY NAME", "00005678", "02/01/24",
         "", "50,000.00", "99,500.00"],
        ["03/01/24", "ATW-XXXXXX1234-NS BLR", "", "03/01/24",
         "2,000.00", "", "97,500.00"],
        ["05/01/24", "UPI-SWIGGY-YESB-67890-", "00006789", "05/01/24",
         "350.00", "", "97,150.00"],
    ]
    with open(file_path, "w", newline="") as f:
        csv.writer(f).writerows(rows)
    return file_path
```

---

## 20. Design Decisions & Rationale

### Why Decimal, not float
Float arithmetic introduces rounding errors with money. `0.1 + 0.2 = 0.30000000000000004`. Bank statements must be precise to the paisa. SQLite TEXT + Python `Decimal` everywhere; SQLAlchemy `TypeDecorator` for the conversion.

### Why pdfplumber, not camelot or tabula
- Camelot's main repo was archived in early 2025.
- Tabula requires a JVM and is heavier.
- pdfplumber gives character-level positional control — essential for HDFC's multi-line narrations.

### Why 3-tier dup detection at import service layer, not a DB UNIQUE constraint
A user might receive two ₹500 UPI payments to the same merchant on the same day with identical narration text. They are legitimately different transactions but would collide on `narration_hash` alone. **Earlier draft used a composite `UNIQUE(account_id, txn_date, amount, narration_hash)` constraint with `INSERT OR IGNORE`. That was wrong** — it silently dropped the second transaction with no signal to the user. Data loss is not an acceptable failure mode.

The fix (v1 plan §11.5): import service runs a 3-tier detector using `reference` and `balance_after` as disambiguators, classifying each incoming row as CLEAN, DEFINITE_DUPLICATE, or AMBIGUOUS. AMBIGUOUS rows get inserted and **both** the new and existing rows are flagged with a shared `dup_group_id` so the user reviews the pair side-by-side and decides. This trades a small UX cost (occasional review prompt) for guaranteed no data loss.

### Why preserve raw fields
If parsing logic improves later (regex bugs, new edge cases), you can re-process from `raw_narration`/`raw_date_str`/`raw_amount_str` without re-importing files. Disk is cheap; user trust is not.

### Why BankConfig + BankAdapter (two layers)
- `BankAdapter` (ABC): public interface — what the rest of the app sees. Stable.
- `BankConfig` (dataclass): internal config inside one adapter — captures all the "this is HDFC's column header text" / "this is HDFC's date format" details. Replaceable.

This separation lets you change a column header without touching the adapter logic, and lets you change the adapter logic without touching the config schema.

---

## 21. Open Questions (decide during implementation)

1. **Statement gap detection:** if you import Jan and Mar but not Feb, the first March transaction's running balance won't reconcile against Jan's last balance. The validator should detect gaps via the `imports` table's `period_start`/`period_end` and skip validation across gaps.

2. **Year rollover for 2-digit dates:** `%d/%m/%y` maps `00-29` to `2000-2029`, `30-99` to `1930-1999`. For HDFC statements from before 1999 this is wrong, but no one uses those. Document and move on.

3. **`statement_period()` implementation:** the placeholder above re-parses the file. For password-protected PDFs this requires the password to already be cached or supplied. Either (a) require the route handler to provide the password again, or (b) cache the decrypted file path during `parse()` and reuse. **Recommendation: (a)** — caches are bug factories.

4. **OCR fallback for scanned PDFs:** explicitly out of v1 scope. If a user uploads a scanned PDF, raise a clear error message pointing them to upload the CSV or a text-based PDF instead.

---

## 22. Future Banks (out of v1 scope, kept for reference)

When SBI or Axis is added later, the procedure is:

1. Create `core/banks/<bankcode>/` package with: `adapter.py`, `config.py`, `pdf_parser.py`, `csv_parser.py`.
2. Define a `BankConfig` for that bank.
3. If multi-line narration is needed (Axis: yes; SBI: no), reuse the merger from `core/banks/hdfc/multiline_merger.py` (or lift it to `core/parsing/`).
4. Implement the adapter — most of the body delegates to the shared CSV/PDF parsers and `normalize_dataframe`.
5. Append the new adapter to `ADAPTERS` in `core/banks/registry.py`.
6. Add fixtures to `tests/fixtures/<bankcode>/` and tests to `tests/test_banks/<bankcode>/`.

### Reference column structures (verify against real statements when implementing)

**SBI Savings — PDF/XLS columns:**
```
Txn Date | Value Date | Description | Ref No./Cheque No. | Debit | Credit | Balance
```
- Date: `D Mon YYYY` (e.g., `2 Jan 2013`) or `DD/MM/YYYY`
- Generally single-line description (no merger needed)
- UPI pattern: `UPI/DR/...` or `UPI/CR/...`
- Email PDF password: last 5 mobile digits + DOB DDMMYY (11 chars)
- NetBanking download password: 11-digit account number

**Axis Savings — PDF columns:**
```
Tran Date | Chq No | Particulars | Debit | Credit | Balance
```
- Date: `DD-MM-YYYY` (e.g., `15-06-2024`)
- Multi-line "Particulars" (similar to HDFC; merger needed)
- Email PDF password: first 4 letters of name (UPPERCASE) + DOB DDMM (e.g., `ROHI1004`)

**These structures are documented from prior research; verify against actual statements before relying on them.**

---

## 23. Handoff to Claude Code

This document is read alongside `finassist-v1-plan.md`. Specifically:

- **For Phase 1 (Foundation):** ignore this document. Phase 1 only needs the v1 plan.
- **For Phase 2 (HDFC Ingestion):** this is the primary reference. Implement modules in this order:
  1. `core/parsing/raw_transaction.py`
  2. `core/parsing/bank_config.py`
  3. `core/parsing/amount_parser.py` + tests
  4. `core/parsing/date_parser.py` + tests
  5. `core/parsing/upi_parser.py` + tests
  6. `core/parsing/decryptor.py`
  7. `core/parsing/normalizer.py`
  8. `core/parsing/balance_validator.py`
  9. `core/banks/base.py` (the BankAdapter ABC from v1 plan §3 — extend to include `account_id` kwarg in `parse()`)
  10. `core/banks/hdfc/config.py`
  11. `core/banks/hdfc/csv_parser.py`
  12. `core/banks/hdfc/pdf_parser.py`
  13. `core/banks/hdfc/multiline_merger.py`
  14. `core/banks/hdfc/adapter.py`
  15. `core/banks/registry.py`
  16. **Schema migration:** add `reference`, `value_date`, `source_file`, `source_page`, `source_line`, `raw_narration`, `raw_date_str`, `raw_amount_str` to `transactions` table (all nullable)
  17. `api/routes/imports.py` — wire registry → adapter → persistence
  18. Frontend: imports page + transactions list page

- **For Phases 3–9:** ignore this document. The classifier, envelopes, subscriptions, etc. are in the v1 plan.

When Phase 2 is complete: tests green, statement upload works for HDFC PDF (with password) and CSV, transactions appear in DB, duplicates rejected on re-upload. Tag commit `phase-2-complete`. Stop. Await review.

---

**End of revised handoff.**
