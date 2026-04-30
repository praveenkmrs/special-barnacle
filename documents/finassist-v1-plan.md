# FinAssist v1 — Implementation Plan

**Personal Finance Assistant — Self-hosted, Local-first, Indian Banking Context**

> Handoff for Claude Code. Build phase-by-phase. Stop and await review at every phase boundary. Do not sprint.

---

## 0. Project Identity

- **Goal:** Local-first personal finance assistant. Track balances across accounts, categorize expenses, detect subscriptions, manage cash envelopes, track investment contributions and growth.
- **Scope (v1):** HDFC Bank only (vertical slice, end-to-end working software).
- **Non-goals (v1):** Other banks, LLM Q&A, goals/forecasting, multi-user auth, mobile UI, OCR for cash receipts, credit card statement line-by-line parsing.
- **Deployment:** Docker Compose on a home laptop. Web UI bound to `127.0.0.1`.
- **Hardware target:** 16GB RAM laptop, CPU-only. No GPU dependence anywhere.

---

## 1. Tech Stack (locked)

| Layer | Choice | Notes |
|---|---|---|
| Backend language | **Python 3.14.4** | Latest stable (released Oct 2025); use `uv` for env mgmt |
| API framework | **FastAPI** | Auto-OpenAPI; async |
| ORM | **SQLAlchemy 2.x** (async) | With Alembic for migrations |
| Database | **SQLite** (WAL mode) | Single file at `~/.finassist/finassist.db` |
| Money type | **`decimal.Decimal`** | Never float. Stored as TEXT in SQLite. |
| PDF parsing | **pdfplumber** + **pikepdf** | Per existing parser handoff doc |
| Tabular | **pandas** | CSV/Excel |
| Fuzzy matching | **scikit-learn** TF-IDF + cosine | For Tier 3 classifier |
| Scheduler | **APScheduler** | Daily NAV fetch |
| Frontend | **React 18 + Vite + TypeScript** | |
| UI library | **Tailwind + shadcn/ui** | Clean, dense, professional |
| Charts | **Tremor** (wraps Recharts) | Built for finance dashboards |
| HTTP client (FE) | **TanStack Query** + **fetch** | |
| Container | **Docker Compose** | services: `api`, `web` |
| Tests | **pytest** + **pytest-asyncio** + **Vitest** | |

---

## 2. Critical Decisions (non-negotiable)

1. **Decimal not float** for all money. SQLite TEXT ↔ Python `Decimal` via SQLAlchemy `TypeDecorator`.
2. **Transfers don't hit P&L.** Categories with `is_transfer=1` excluded from income/expense aggregations.
3. **Cash envelopes are first-class accounts.** ATM withdrawal = inter-account transfer, not expense.
4. **Investments dual-write.** SIP debit creates BOTH a transaction (category Investment-SIP) AND a holding_transaction (buy), linked via `linked_transaction_id`.
5. **No auth in v1.** API binds `127.0.0.1` only. Migration path: drop auth middleware later.
6. **CSV export mandatory.** Per-table dumps available from day one.
7. **All amounts in INR.** Multi-currency deferred indefinitely.
8. **Three "savings" labels — never use the word "savings":**
   - **Cash Buffer** = sum of bank + cash envelope balances at point in time
   - **Capital Deployed** = total invested cost across holdings
   - **Net Cashflow** = income − expenses for selected period
9. **Bank-adapter pattern.** All bank-specific logic lives behind a `BankAdapter` interface. Adding a new bank = adding a new adapter package; zero changes to core classifier/analytics/UI.

---

## 3. Bank Adapter Architecture

To make future bank additions clean, all bank-specific behavior is isolated.

### Interface (Python)

```python
# core/banks/base.py
from abc import ABC, abstractmethod
from pathlib import Path
from datetime import date
from core.models import RawTransaction

class BankAdapter(ABC):
    bank_code: str          # e.g. "HDFC"
    display_name: str       # e.g. "HDFC Bank"
    supported_formats: list[str]   # ["pdf", "csv", "xlsx"]

    @abstractmethod
    def detect(self, file_path: Path) -> bool:
        """Return True if this adapter recognizes the file."""

    @abstractmethod
    def parse(self, file_path: Path, password: str | None = None) -> list[RawTransaction]:
        """Parse statement file → list of normalized RawTransaction."""

    @abstractmethod
    def statement_period(self, file_path: Path) -> tuple[date, date]:
        """Return (start_date, end_date) covered by this statement."""
```

### Registry

```python
# core/banks/registry.py
ADAPTERS: list[BankAdapter] = [HDFCAdapter()]   # add SBIAdapter() etc later

def detect_bank(file_path: Path) -> BankAdapter | None:
    return next((a for a in ADAPTERS if a.detect(file_path)), None)
```

### Adding a new bank later (the entire procedure)

1. Create `core/banks/<bankcode>/` package.
2. Implement `<BankCode>Adapter(BankAdapter)`.
3. Append to `ADAPTERS` list.
4. Add fixture statements to `tests/fixtures/<bankcode>/`.
5. Add adapter unit tests.

No other code changes. UI and classifier are bank-agnostic.

### HDFC statement structure (v1 target)

**PDF format (most common):**
- Encrypted by default; password is typically `<PAN>DDMMYYYY` (DOB) or first 4 letters of name + DOB.
- Tabular columns: `Date | Narration | Chq./Ref.No. | Value Dt | Withdrawal Amt. | Deposit Amt. | Closing Balance`.
- **Multi-line narration problem:** A single transaction's narration wraps across multiple PDF table rows. Continuation rows have empty Date column. Must merge BEFORE column normalization.
- Indian number formatting: `1,00,000.00` (lakh-grouped, not thousand-grouped). Standard parsers fail here.
- Date format: `DD/MM/YY`.
- Page footer: account number, statement period, IFSC.
- UPI narrations are semi-structured: `UPI-<PAYEE>-<UPIID>-<BANK>-<REFNO>-<NOTE>`.

**CSV format (preferred when available):**
- Downloaded from HDFC NetBanking. Cleaner than PDF.
- Tab or comma delimited (varies). Auto-detect required.
- Same columns as PDF but no multi-line narration issue.

**Edge cases to handle:**
- Multi-line narration (the big one)
- Indian number formatting (`,` as both thousand and lakh separator)
- Salary credit narrations vary monthly (employer payroll IDs)
- Reversed/refunded transactions appear as positive credits with "REVERSAL" or "REF" tokens
- ATM withdrawals: narration prefix `ATW` or `NWD`
- IMPS/NEFT/RTGS prefixes for inter-bank transfers

---

## 4. Schema (SQLite DDL)

```sql
-- ============================================================
-- Accounts: real banks, credit cards, brokers, virtual cash envelopes
-- ============================================================
CREATE TABLE accounts (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL CHECK(type IN ('bank','credit_card','cash_envelope','broker','mf','epf','nps')),
  bank_code TEXT,                             -- 'HDFC','SBI','AXIS'; null for envelopes
  account_number_masked TEXT,
  envelope_owner TEXT,                        -- Mom/Dad/Wife/Daughter/Self for cash_envelope
  currency TEXT NOT NULL DEFAULT 'INR',
  is_active INTEGER NOT NULL DEFAULT 1,
  opening_balance TEXT NOT NULL DEFAULT '0',  -- Decimal as TEXT
  opening_balance_date DATE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- Categories: two-level via parent_id; self-ref allows deeper trees later
-- ============================================================
CREATE TABLE categories (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  parent_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
  is_transfer INTEGER NOT NULL DEFAULT 0,     -- excluded from P&L
  is_income INTEGER NOT NULL DEFAULT 0,
  display_order INTEGER DEFAULT 100,
  UNIQUE(name, parent_id)
);

-- ============================================================
-- Subscriptions: logical owner of recurring transactions
-- ============================================================
CREATE TABLE subscriptions (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  expected_amount TEXT,                       -- Decimal as TEXT
  amount_tolerance_pct REAL NOT NULL DEFAULT 5.0,
  cadence TEXT CHECK(cadence IN ('monthly','quarterly','annual','custom')),
  next_expected_date DATE,
  status TEXT NOT NULL CHECK(status IN ('active','paused','cancelled')) DEFAULT 'active',
  category_id INTEGER REFERENCES categories(id),
  account_id INTEGER REFERENCES accounts(id),
  started_on DATE,
  ended_on DATE,
  notes TEXT,
  auto_detected INTEGER NOT NULL DEFAULT 0
);

-- ============================================================
-- Transactions: single source of truth
-- ============================================================
CREATE TABLE transactions (
  id INTEGER PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES accounts(id),
  txn_date DATE NOT NULL,
  amount TEXT NOT NULL,                       -- Decimal as TEXT
  type TEXT NOT NULL CHECK(type IN ('debit','credit')),
  narration TEXT NOT NULL,
  narration_hash TEXT NOT NULL,               -- SHA-256 of normalized narration
  balance_after TEXT,
  reference TEXT,                             -- bank ref / cheque no; key disambiguator for dup detection
  value_date DATE,                            -- value date when different from txn_date
  category_id INTEGER REFERENCES categories(id),
  subscription_id INTEGER REFERENCES subscriptions(id),
  transfer_pair_id INTEGER REFERENCES transactions(id),  -- other leg of transfer
  is_transfer INTEGER NOT NULL DEFAULT 0,
  classification_source TEXT CHECK(classification_source IN ('rule_t1','rule_t2','fuzzy_t3','manual','unclassified')),
  classification_confidence REAL,
  needs_review INTEGER NOT NULL DEFAULT 0,
  notes TEXT,
  dup_group_id INTEGER,                       -- non-null = part of a duplicate review pair/group
  review_reason TEXT CHECK(review_reason IN ('classification','duplicate','transfer')),
  -- Source provenance (populated by parser; used for debugging and re-parsing)
  source_file TEXT,
  source_page INTEGER,
  source_line INTEGER,
  raw_narration TEXT,
  raw_date_str TEXT,
  raw_amount_str TEXT,
  imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  -- NOTE: No UNIQUE constraint on (account_id, txn_date, amount, narration_hash).
  -- Uniqueness is enforced by the import service (see §11.5). Hard UNIQUE would
  -- silently drop legitimate same-day same-amount same-merchant transactions.
);
CREATE INDEX idx_txn_date ON transactions(txn_date);
CREATE INDEX idx_txn_category ON transactions(category_id);
CREATE INDEX idx_txn_subscription ON transactions(subscription_id);
CREATE INDEX idx_txn_review ON transactions(needs_review) WHERE needs_review=1;
CREATE INDEX idx_txn_account_date ON transactions(account_id, txn_date);
CREATE INDEX idx_txn_dup_group ON transactions(dup_group_id) WHERE dup_group_id IS NOT NULL;
-- Used for fast duplicate-detection lookups during import:
CREATE INDEX idx_txn_dedup_lookup ON transactions(account_id, txn_date, amount, narration_hash);

-- ============================================================
-- Rules: classification rules (deterministic + candidate)
-- ============================================================
CREATE TABLE rules (
  id INTEGER PRIMARY KEY,
  pattern TEXT NOT NULL,                      -- regex on narration
  pattern_type TEXT CHECK(pattern_type IN ('narration','vpa','prefix','token','exact')),
  amount_min TEXT,                            -- nullable
  amount_max TEXT,                            -- nullable
  account_id INTEGER REFERENCES accounts(id), -- null = all accounts
  txn_type TEXT CHECK(txn_type IN ('debit','credit')),  -- null = both
  category_id INTEGER REFERENCES categories(id),
  subscription_id INTEGER REFERENCES subscriptions(id),
  status TEXT NOT NULL CHECK(status IN ('candidate','active','disabled','blacklisted')) DEFAULT 'candidate',
  priority INTEGER NOT NULL DEFAULT 100,
  hit_count INTEGER NOT NULL DEFAULT 0,
  conflict_count INTEGER NOT NULL DEFAULT 0,
  last_hit_at TIMESTAMP,
  created_by TEXT NOT NULL CHECK(created_by IN ('system','user')),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  promoted_at TIMESTAMP,
  blacklist_until TIMESTAMP                   -- 90-day cooldown after 3 conflicts
);
CREATE INDEX idx_rules_status ON rules(status);
CREATE INDEX idx_rules_priority ON rules(priority);

-- ============================================================
-- Holdings: investment positions
-- ============================================================
CREATE TABLE holdings (
  id INTEGER PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES accounts(id),
  instrument_type TEXT NOT NULL CHECK(instrument_type IN ('mf','stock','fd','epf','nps','crypto')),
  identifier TEXT NOT NULL,                   -- ISIN / AMFI scheme code / NSE symbol
  name TEXT NOT NULL,
  units TEXT NOT NULL DEFAULT '0',
  avg_cost TEXT,
  total_invested TEXT NOT NULL DEFAULT '0',   -- running sum of buys − sells
  current_nav TEXT,
  current_value TEXT,                         -- units * current_nav
  nav_updated_at TIMESTAMP,
  UNIQUE(account_id, identifier)
);

CREATE TABLE holding_transactions (
  id INTEGER PRIMARY KEY,
  holding_id INTEGER NOT NULL REFERENCES holdings(id),
  txn_date DATE NOT NULL,
  type TEXT NOT NULL CHECK(type IN ('buy','sell','dividend','split','bonus')),
  units TEXT NOT NULL,
  price_per_unit TEXT,
  amount TEXT NOT NULL,
  linked_transaction_id INTEGER REFERENCES transactions(id),
  notes TEXT
);

-- ============================================================
-- Imports: audit + gap detection
-- ============================================================
CREATE TABLE imports (
  id INTEGER PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES accounts(id),
  source_file TEXT,
  source_format TEXT CHECK(source_format IN ('pdf','csv','xlsx','manual')),
  bank_code TEXT,
  period_start DATE,
  period_end DATE,
  rows_imported INTEGER NOT NULL DEFAULT 0,
  rows_duplicate INTEGER NOT NULL DEFAULT 0,
  rows_failed INTEGER NOT NULL DEFAULT 0,
  status TEXT CHECK(status IN ('success','partial','failed')),
  error_log TEXT,
  imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- NAV cache: AMFI daily snapshot
-- ============================================================
CREATE TABLE nav_cache (
  id INTEGER PRIMARY KEY,
  scheme_code TEXT NOT NULL,
  scheme_name TEXT,
  nav TEXT NOT NULL,
  nav_date DATE NOT NULL,
  fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(scheme_code, nav_date)
);
```

---

## 5. Default Category Taxonomy (seed data)

```
Income (is_income=1)
  ├── Salary
  ├── Interest
  ├── Dividends
  ├── Capital Gains
  ├── Refunds
  └── Other Income

Housing
  ├── Rent
  ├── Maintenance/Society
  ├── Utilities-Electricity
  ├── Utilities-Water
  ├── Utilities-Gas
  ├── Utilities-Internet
  └── Repairs

Food
  ├── Groceries
  ├── Eating Out
  ├── Food Delivery
  └── Beverages/Cafe

Transport
  ├── Fuel
  ├── Cab/Auto
  ├── Public Transit
  ├── Vehicle Maintenance
  ├── Parking/Toll
  └── Travel-Long Distance

Health
  ├── Doctor/Consultation
  ├── Pharmacy
  ├── Diagnostics
  ├── Insurance Premium-Health
  └── Fitness/Gym

Family
  ├── Pocket Money - Mom
  ├── Pocket Money - Dad
  ├── Pocket Money - Wife
  ├── Pocket Money - Daughter
  ├── Self - Personal Cash
  ├── Family Support/Remittance
  ├── Childcare/School Fees
  └── Gifts

Personal
  ├── Clothing
  ├── Personal Care
  ├── Entertainment
  └── Hobbies

Subscriptions
  ├── OTT
  ├── Music
  ├── Cloud/Software
  ├── News/Reading
  └── Other Recurring

Financial
  ├── Investment-SIP
  ├── Investment-Lumpsum
  ├── Investment-Stocks
  ├── Investment-FD
  ├── Insurance Premium-Life
  ├── Insurance Premium-Vehicle
  ├── Loan-EMI
  ├── Credit Card Bill Payment
  └── Bank Fees/Charges

Taxes
  ├── Income Tax
  ├── GST
  └── Property Tax

Transfers (is_transfer=1)
  ├── Inter-account Transfer
  ├── Cash Withdrawal (to envelope)
  └── Reimbursement

Uncategorized
```

---

## 6. Module Layout

```
finassist/
├── pyproject.toml                # uv-managed; Python 3.14
├── docker-compose.yml
├── Dockerfile.api
├── Dockerfile.web
├── api/                          # FastAPI app
│   ├── main.py
│   ├── deps.py                   # DB session, settings
│   ├── routes/
│   │   ├── accounts.py
│   │   ├── transactions.py
│   │   ├── categories.py
│   │   ├── rules.py
│   │   ├── subscriptions.py
│   │   ├── envelopes.py
│   │   ├── holdings.py
│   │   ├── imports.py
│   │   ├── analytics.py
│   │   └── exports.py
│   └── schemas/                  # Pydantic models
├── core/
│   ├── banks/
│   │   ├── base.py               # BankAdapter ABC
│   │   ├── registry.py           # ADAPTERS list + detect_bank()
│   │   └── hdfc/
│   │       ├── __init__.py       # HDFCAdapter
│   │       ├── pdf_parser.py
│   │       ├── csv_parser.py
│   │       ├── multiline_merger.py
│   │       └── config.py         # column maps, date format, password hint
│   ├── parsing/
│   │   ├── normalize.py          # Indian number, Decimal coercion
│   │   ├── dates.py              # multi-format date parsing
│   │   ├── upi.py                # UPI narration sub-parser
│   │   ├── decryptor.py          # pikepdf wrapper
│   │   └── dedup.py              # narration_hash + composite key
│   ├── classifier/
│   │   ├── tier1_rules.py
│   │   ├── tier2_candidates.py
│   │   ├── tier3_fuzzy.py
│   │   ├── pipeline.py           # orchestrator
│   │   ├── pattern_extractor.py  # narration → candidate patterns
│   │   └── promoter.py           # candidate → active promotion logic
│   ├── envelopes/
│   │   └── service.py            # ATM split, manual debit
│   ├── imports/
│   │   ├── service.py            # ingest pipeline orchestrator
│   │   └── duplicate_detector.py # 3-tier dup detection (see §11.5)
│   ├── subscriptions/
│   │   ├── detector.py           # cadence + amount-window detection
│   │   └── linker.py             # auto-link new txns to subscriptions
│   ├── investments/
│   │   ├── nav_fetcher.py        # AMFI NAVAll.txt
│   │   ├── holdings_service.py
│   │   └── valuation.py
│   ├── transfers/
│   │   └── pair_matcher.py       # debit-credit pairing within 72h
│   └── analytics/
│       ├── aggregations.py
│       ├── forecasts.py          # commitment-model only
│       └── balances.py
├── db/
│   ├── schema.sql                # full DDL
│   ├── seeds.sql                 # default categories
│   ├── migrations/               # alembic
│   └── models.py                 # SQLAlchemy
├── tests/
│   ├── fixtures/
│   │   └── hdfc/                 # sample PDF/CSV statements
│   ├── test_banks/
│   ├── test_parsing/
│   ├── test_classifier/
│   ├── test_envelopes/
│   └── test_api/
└── web/                          # React frontend
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.ts
    ├── src/
    │   ├── main.tsx
    │   ├── App.tsx
    │   ├── routes/
    │   │   ├── Dashboard.tsx
    │   │   ├── Transactions.tsx
    │   │   ├── ReviewQueue.tsx
    │   │   ├── Categories.tsx
    │   │   ├── Rules.tsx
    │   │   ├── Subscriptions.tsx
    │   │   ├── Envelopes.tsx
    │   │   ├── Holdings.tsx
    │   │   ├── Imports.tsx
    │   │   └── Settings.tsx
    │   ├── components/
    │   │   ├── ui/               # shadcn primitives
    │   │   ├── charts/           # Tremor wrappers
    │   │   └── layout/
    │   ├── lib/
    │   │   ├── api.ts            # fetch wrapper
    │   │   └── decimal.ts        # decimal.js for client-side money
    │   └── hooks/
```

---

## 7. Classification Engine Spec

### Pipeline (every new/imported transaction)

1. **Tier 1 — Active rules**
   - Query: `rules WHERE status='active' AND (account_id IS NULL OR account_id=:acc) AND (txn_type IS NULL OR txn_type=:type)`.
   - Filter further by amount range if set.
   - Order by `priority ASC, length(pattern) DESC`. First regex match wins.
   - Set: `category_id`, `classification_source='rule_t1'`, `classification_confidence=1.0`, `needs_review=0`.
   - Increment `rules.hit_count`, set `last_hit_at`.

2. **Tier 2 — Candidate rules** (only if Tier 1 didn't match)
   - Same query but `status='candidate'`.
   - On match: classify, but `needs_review=1`, `confidence=0.85`, source `'rule_t2'`.
   - Promotion check (run nightly + on every hit):
     - If `hit_count >= 5 OR (now − created_at) >= 30 days` AND `conflict_count = 0`:
     - `status='active'`, `promoted_at=now`. Affected past txns: `needs_review=0`.

3. **Tier 3 — Fuzzy fallback** (only if Tier 1+2 didn't match)
   - TF-IDF vectorize all manually-classified narrations + new narration.
   - Cosine similarity → top-3 categories.
   - If top similarity > 0.85 → auto-classify, source `'fuzzy_t3'`, `confidence=similarity`, `needs_review=0`.
   - Else → `needs_review=1`, attach top-3 suggestions in `notes` field.

### Pattern extraction (on manual classification)

When user classifies a transaction manually, generate candidate patterns at multiple granularities:
- **Prefix:** first 20 chars of narration (escaped regex)
- **Top-IDF token:** highest-IDF word from narration
- **VPA pattern:** if narration contains `@`, extract `*@handle` form
- **UPI handle:** if narration matches `UPI/<merchant>/...` or `UPI-<merchant>-...`, extract merchant token

Each pattern, upsert into `rules` with `status='candidate'`, `created_by='user'`. Most specific (longest) wins.

### Conflict handling

- If user re-classifies an auto-classified transaction: increment `conflict_count` on the offending T1/T2 rule (T3 has no rule row).
- 3 conflicts → `status='disabled'`, `blacklist_until=now+90d`.
- Patterns in blacklist window cannot be re-promoted.

### Manual rule management

- Full CRUD via API and UI.
- Manual edits flip `created_by='user'` and bypass probation (status can be set directly to `active`).
- Maintenance view: list rules sorted by `last_hit_at DESC NULLS FIRST`; flag dead rules (no hit in 90 days).

---

## 8. Cash Envelope System

### Concept

Withdrawal of ₹20,000 from HDFC ATM, then handed out:
- ₹5,000 → Mom, ₹5,000 → Wife, ₹3,000 → Daughter, ₹2,000 → Self, ₹5,000 retained in HDFC.

### Implementation

1. ATM withdrawal arrives in HDFC statement. Parser flags it (narration contains `ATW`/`NWD`/`ATM`/`CASH WDL`).
2. UI shows withdrawal in review queue with "Split into envelopes" action.
3. User splits ₹15,000 across 4 envelopes. System creates:
   - Original HDFC debit, category = "Inter-account Transfer", `is_transfer=1`.
   - 4 transactions on envelope accounts (credit type), category = "Inter-account Transfer", paired via `transfer_pair_id`.
4. When user reports family spent cash (manual entry): debit on envelope account with appropriate expense category.

### Net effect

- ATM withdrawal: zero P&L impact (transfer).
- Family spending (manual): hits expense category.
- Envelope balance = sum of credits − sum of debits on that envelope account.

---

## 9. Subscription Detection

### Auto-detection algorithm (run nightly + on import)

1. Group transactions by `(account_id, narration_hash)` over last 6 months.
2. For each group with ≥2 occurrences:
   - Compute median amount; check all amounts within ±5%.
   - Compute date diffs; classify cadence:
     - Median diff 28-32 days → monthly
     - 88-95 days → quarterly
     - 360-370 days → annual
3. If matches: create `subscriptions` row with `auto_detected=1`, `next_expected_date = last_seen + median_diff`. Link past transactions via `transaction.subscription_id`.

### Manual subscription mgmt

- Create/edit/delete subscription with name, expected amount, cadence, account.
- Tag any transaction to a subscription (manual override).
- Subscription detail page shows ALL linked transactions + projected next 12 months.

### Upcoming view

For each active subscription: `next_expected_date` + (cadence × n) for next 12 months. Sum = annual run-rate.

---

## 10. Investment Tracking

### Data sources

| Asset class | Source | Frequency |
|---|---|---|
| Mutual funds | AMFI `NAVAll.txt` (`https://www.amfiindia.com/spages/NAVAll.txt`) | Daily after 23:00 IST |
| Indian stocks | Manual entry (v1); NSE bhavcopy later | EOD |
| FDs | No API; principal × rate × time-elapsed | Computed |
| EPF | Manual quarterly update | Manual |

### Flow: SIP debit example

1. HDFC statement shows ₹10,000 debit `ACH D- HDFC AMC- ...`.
2. Tier 1/2 rule classifies as category "Investment-SIP".
3. User (or auto-link via subscription) attaches it to a holding record.
4. System creates `holding_transactions` row: `type='buy'`, looks up scheme NAV for that date from `nav_cache`, computes units, updates `holdings.units` and `holdings.total_invested`.
5. Transaction's `linked_transaction_id` points back. Single source, two views.

### NAV fetcher

- APScheduler cron: daily 23:30 IST.
- Download AMFI NAVAll.txt, parse pipe-delimited format, upsert into `nav_cache`.
- After cache update: recompute `holdings.current_nav`, `current_value` for all MF holdings.

---

## 11. Transfer Detection

Run on every import:

1. Find debit-credit pairs across different accounts where:
   - Amounts equal (exact)
   - Dates within 72 hours
   - Both unclassified or both already in transfer category
2. Mark both with `is_transfer=1`, link via `transfer_pair_id`, set `needs_review=1`.
3. UI shows pending transfer pairs for confirmation.
4. User confirms → `needs_review=0`. Rejects → `is_transfer=0`, transfer_pair_id cleared.

---

## 11.5 Duplicate Detection (import-time)

**Why it exists:** Two genuine same-day same-amount same-merchant transactions (e.g., two ₹100 coffees from the same shop) collide on `(account_id, txn_date, amount, narration_hash)`. A hard UNIQUE constraint would silently drop the second one — losing real data. Instead, the import service runs a three-tier detection and queues ambiguous cases for review. **Both** transactions get flagged so the user can compare them side-by-side and decide.

### Detection logic (per incoming RawTransaction)

For each incoming transaction, query existing rows matching `(account_id, txn_date, amount, type, narration_hash)`. If no match → clean insert, done.

If at least one match exists, classify the relationship:

**Tier A — Definite duplicate (silently skip):**
- Reference numbers both present AND equal, OR
- `balance_after` both present AND equal

Reasoning: HDFC reference numbers are unique per transaction, so equal references mean the same transaction was imported twice (typical re-import case). Equal `balance_after` is also a strong signal — two genuinely separate ₹100 transactions on the same day would necessarily produce different running balances.

Action: increment `imports.rows_duplicate`, do not insert. Log silently.

**Tier B — Definitely not a duplicate (clean insert):**
- Reference numbers both present AND differ, OR
- `balance_after` both present AND differ

Action: insert with no flag.

**Tier C — Ambiguous (insert + queue both for review):**
- All other cases (e.g., reference null on one or both, balance null on one or both, mixed presence).

Action:
1. Allocate a new `dup_group_id` (max(existing) + 1, or sequence).
2. Set `dup_group_id` on the **existing** matched row(s) AND the new row.
3. Set `needs_review=1` and `review_reason='duplicate'` on all of them.
4. Insert the new row normally.

### Review UX

- Review queue page has a "Possible duplicates" tab.
- Each duplicate group renders as a single card showing all rows in the group side-by-side (date, amount, narration, reference, balance, source_file, source_page).
- User actions:
  - **"Keep all as legitimate"** → clear `dup_group_id` and `review_reason` on every row, set `needs_review=0`.
  - **"Mark as duplicate"** with a row selection → delete the selected row(s); on remaining row, clear `dup_group_id`, `review_reason`, and `needs_review`.
- Optional: **"Always merge for this merchant"** — creates a user rule that promotes Tier C → Tier A for future imports matching this narration pattern. Stored in the `rules` table with a special action type. (Defer to v1.5 if it complicates Phase 2.)

### Implementation skeleton

```python
# core/imports/duplicate_detector.py

from enum import Enum
from dataclasses import dataclass

from core.parsing.models import RawTransaction


class DupVerdict(Enum):
    CLEAN = "clean"              # no match found OR matches confirm distinctness
    DEFINITE_DUPLICATE = "definite_duplicate"   # silently skip
    AMBIGUOUS = "ambiguous"      # insert + flag both for review


@dataclass
class DupCheckResult:
    verdict: DupVerdict
    matched_existing_ids: list[int]  # IDs of existing rows that match the dedup key


def check_duplicate(
    incoming: RawTransaction,
    account_id: int,
    db_session,
) -> DupCheckResult:
    """
    Returns the verdict for an incoming transaction against the database.
    Caller is responsible for the actual insert + flag operations.
    """
    matches = db_session.execute(
        """
        SELECT id, reference, balance_after
        FROM transactions
        WHERE account_id = :acc
          AND txn_date   = :dt
          AND amount     = :amt
          AND type       = :typ
          AND narration_hash = :hash
        """,
        {
            "acc": account_id,
            "dt": incoming.txn_date,
            "amt": str(incoming.amount),
            "typ": incoming.type.value,
            "hash": incoming.narration_hash,
        },
    ).fetchall()

    if not matches:
        return DupCheckResult(DupVerdict.CLEAN, [])

    # Tier A: definite duplicate (any single match confirms re-import)
    for m in matches:
        if incoming.reference and m.reference and incoming.reference == m.reference:
            return DupCheckResult(DupVerdict.DEFINITE_DUPLICATE, [m.id])
        if incoming.balance_after is not None and m.balance_after is not None:
            if str(incoming.balance_after) == m.balance_after:
                return DupCheckResult(DupVerdict.DEFINITE_DUPLICATE, [m.id])

    # Tier B: definitely distinct (any single confident "no" is enough)
    for m in matches:
        if incoming.reference and m.reference and incoming.reference != m.reference:
            return DupCheckResult(DupVerdict.CLEAN, [])
        if incoming.balance_after is not None and m.balance_after is not None:
            if str(incoming.balance_after) != m.balance_after:
                return DupCheckResult(DupVerdict.CLEAN, [])

    # Tier C: ambiguous — flag for review with all matches
    return DupCheckResult(DupVerdict.AMBIGUOUS, [m.id for m in matches])
```

The import service consumes this verdict:

```python
# core/imports/service.py (sketch)

def ingest_transaction(incoming: RawTransaction, account_id: int, db) -> str:
    result = check_duplicate(incoming, account_id, db)

    if result.verdict is DupVerdict.DEFINITE_DUPLICATE:
        return "skipped_duplicate"

    if result.verdict is DupVerdict.CLEAN:
        insert_transaction(incoming, account_id, db, needs_review=False)
        return "inserted_clean"

    # Ambiguous: insert + flag both
    new_id = insert_transaction(
        incoming, account_id, db, needs_review=True, review_reason="duplicate"
    )
    dup_group_id = new_id  # use new row's ID as the group anchor; or allocate from sequence

    db.execute(
        "UPDATE transactions SET dup_group_id = :g WHERE id IN :ids",
        {"g": dup_group_id, "ids": tuple(result.matched_existing_ids + [new_id])},
    )
    db.execute(
        "UPDATE transactions SET needs_review = 1, review_reason = 'duplicate' "
        "WHERE id IN :ids",
        {"ids": tuple(result.matched_existing_ids)},
    )
    return "inserted_ambiguous"
```

### Edge cases addressed

- **Same statement re-imported** → reference numbers match → Tier A → silent skip. No review queue spam.
- **Two real coffees same day** → references differ (or both null) AND balances differ → Tier B → both present, no review.
- **Two real coffees same day, no references, no balances** → Tier C → flagged. User reviews, sees both rows, picks "Keep all".
- **Statement edited and re-imported with corrections** → references same but balance differs (because earlier rows changed) → Tier A wins (reference is more authoritative). User can manually delete and re-import if they want the corrections applied.
- **Three or more colliding rows** → all join the same `dup_group_id`. Review card shows all of them.

## 12. Build Phases

> **STOP at every phase boundary. Run tests. Demo to user. Await go-ahead.**

### Phase 1 — Foundation
**Acceptance:** `docker compose up` starts api + web. API health endpoint returns 200. Web shows empty dashboard shell with all routes accessible. SQLite DB initialized with schema + seed categories. CSV export endpoint returns empty CSV. `Decimal` TypeDecorator unit-tested.

- Project scaffolding (`pyproject.toml` with Python 3.14, `package.json`)
- Docker Compose with api + web services
- FastAPI app with `/health` route
- SQLAlchemy models + Decimal TypeDecorator + Alembic baseline migration
- React app with shadcn/ui + Tailwind + Tremor + TanStack Query + routing
- Empty page shells for all 10 routes
- Seed default categories on first boot
- CSV export endpoints (transactions, accounts, categories)

### Phase 2 — HDFC Ingestion
**Acceptance:** Upload an HDFC PDF statement (encrypted, with multi-line narration); transactions appear in DB; duplicate detection runs the 3-tier logic from §11.5 (definite dups silently skipped, ambiguous cases flagged for review with both rows linked via `dup_group_id`); transactions list page shows them. CSV import also works. `BankAdapter` interface in place even though only HDFC is implemented.

- `BankAdapter` ABC + registry
- HDFC adapter package: PDF parser, CSV parser, multi-line merger, config
- pikepdf decryptor with password prompt UX
- Indian number/date normalizers
- UPI narration sub-parser
- Manual statement upload endpoint (`POST /imports`)
- **Three-tier duplicate detector** (§11.5): definite/ambiguous/clean classification
- **Duplicate review group creation** (sets `dup_group_id`, `review_reason='duplicate'`, `needs_review=1`)
- Statement gap detection (period overlap analysis)
- Transactions list page (filterable by date, account, category)
- Imports history page

### Phase 3 — Classification
**Acceptance:** Manually classify 5 transactions; candidate rules generated; future imports auto-classify those merchants; review queue shows low-confidence classification items with top-3 suggestions; review queue ALSO renders duplicate groups (from §11.5) as side-by-side comparison cards with "Keep all" / "Mark as duplicate" actions; rules CRUD works in UI.

- Tier 1/2/3 pipeline implementation
- Pattern extractor (4 granularities)
- Candidate promoter (5-hits-or-30-days, conflict tracking)
- TF-IDF fuzzy fallback
- Rules CRUD API + UI
- Review queue page with batch-classify UX
- **Duplicate review pane** rendering grouped rows from `dup_group_id`
- Maintenance view (dead rules, hit counts)

### Phase 4 — Cash Envelopes
**Acceptance:** Create 5 envelopes (Mom/Dad/Wife/Daughter/Self); split an ATM withdrawal across them; manually log cash spend on Mom's envelope; envelope balance reflects correctly.

- Envelope account creation (type=cash_envelope)
- ATM withdrawal split UI
- Manual envelope debit entry
- Envelope balance computation in analytics
- Envelopes page

### Phase 5 — Subscriptions
**Acceptance:** After importing 6 months of data, system auto-detects ≥3 subscriptions; user can create custom subscription, link transactions; subscription detail page shows all linked txns + next 12 months forecast; upcoming view shows annual run-rate.

- Auto-detection algorithm
- Subscriptions CRUD
- Transaction → subscription linking (manual + auto)
- Subscription detail page
- Upcoming view (commitment-model forecast)

### Phase 6 — Investments
**Acceptance:** Create 3 MF holdings manually; NAV fetcher pulls AMFI data; holdings show current value; SIP transaction flow auto-creates holding_transaction (buy) and updates units.

- Holdings CRUD
- AMFI NAV fetcher (APScheduler daily job + manual trigger button)
- holding_transaction creation flow
- Holdings page with cost vs current value display
- FD interest calculator (principal × rate × elapsed)

### Phase 7 — Dashboard
**Acceptance:** Dashboard shows three top tiles (Cash Buffer, Capital Deployed, Net Cashflow), per-account balances, expense donut by category with drill-down, subscription panel, review queue badge. Time-window selector (default 3 months) re-renders all widgets.

- Dashboard layout (per wireframe in §14)
- Time-window selector with URL state
- Per-account balance tiles
- Category expense breakdown (donut + table with % change vs previous period)
- Subscription run-rate panel
- Review queue badge

### Phase 8 — Transfer Detection
**Acceptance:** After importing two account statements with a real transfer, system flags the pair; user confirms; both transactions marked `is_transfer=1`; P&L excludes them.

- Pair-matcher implementation
- Transfer review queue
- Manual override

### Phase 9 — Polish
**Acceptance:** All entities exportable to CSV; rule maintenance view usable; settings page allows category/envelope/subscription mgmt; all forms have validation; error states handled; README documents setup.

- CSV export per entity finalized
- Rule maintenance view polish
- Settings page
- Error/empty states everywhere
- README + setup docs
- One Playwright happy-path E2E test

**END OF v1.**

### Future expansions (not in v1, but architecture supports)

- **More banks:** SBI, Axis, ICICI, Kotak adapters. Just implement `BankAdapter` and register.
- **Credit card statement parsing** as dedicated entity.
- **NSE/BSE bhavcopy integration** for stock prices.
- **Goals & forecasting layer.**
- **AI Q&A layer** (deferred entirely; can plug in later as a separate service).
- **Mobile-responsive UI.**
- **Multi-currency.**

---

## 13. API Surface (key routes)

```
GET    /health
GET    /accounts                  POST /accounts                PATCH /accounts/{id}
GET    /transactions              POST /transactions/{id}/classify
GET    /transactions/review-queue
GET    /categories                POST /categories
GET    /rules                     POST /rules                   PATCH /rules/{id}
POST   /rules/{id}/promote        POST /rules/{id}/disable
GET    /subscriptions             POST /subscriptions           PATCH /subscriptions/{id}
GET    /subscriptions/{id}/transactions
GET    /envelopes                 POST /envelopes/split         POST /envelopes/{id}/debit
GET    /holdings                  POST /holdings                POST /holdings/refresh-nav
POST   /imports                   GET /imports
GET    /transfers/candidates      POST /transfers/{id}/confirm  POST /transfers/{id}/reject
GET    /duplicates/groups         POST /duplicates/{group_id}/keep-all
POST   /duplicates/{group_id}/resolve   # body: {keep_ids: [int], delete_ids: [int]}
GET    /analytics/dashboard?from=&to=
GET    /analytics/categories?from=&to=
GET    /analytics/cashflow?from=&to=
GET    /exports/transactions.csv
GET    /exports/{entity}.csv
```

---

## 14. Dashboard Wireframe

```
┌─────────────────────────────────────────────────────────────────┐
│  [Time: Last 3 months ▼]  [Account: All ▼]   [Import] [Export]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  CASH BUFFER         CAPITAL DEPLOYED      NET CASHFLOW (3mo)   │
│  ₹1,93,479           Cost ₹4,50,000        +₹38,250             │
│  across 5 accounts   Value ₹4,87,300       income − expense     │
│                      (+8.3%)                                    │
│                                                                 │
├──────────────────────────────────┬──────────────────────────────┤
│  ACCOUNTS                        │  REVIEW QUEUE        [12 →]  │
│  HDFC Salary       ₹1,23,456     │  Last imported: Apr 25, 2026 │
│  Cash:Mom          ₹   5,000     │  Statement gaps: none        │
│  Cash:Wife         ₹   8,000     │                              │
│  Cash:Daughter     ₹   3,000     │  UPCOMING (next 30 days)     │
│  Cash:Self         ₹   2,000     │  Netflix      ₹649    May 3  │
│  ─────────                       │  SIP-Flexicap ₹10,000 May 5  │
│  Holdings (MF)     ₹4,87,300     │  Rent         ₹35,000 May 1  │
│                                  │  ─────────                   │
│                                  │  Total: ₹46,499              │
│                                  │  Annual run-rate: ₹5,57,988  │
├──────────────────────────────────┴──────────────────────────────┤
│  EXPENSES BY CATEGORY (click → drill into transactions)         │
│  [Donut chart]                                                  │
│  Food         ₹18,400  ↑12%                                     │
│  Transport    ₹ 9,200  ↓5%                                      │
│  Family       ₹15,000  ─                                        │
│  Subscriptions ₹3,847  ↑2%                                      │
│  ...                                                            │
├─────────────────────────────────────────────────────────────────┤
│  SUBSCRIPTIONS (annual run-rate: ₹46,488)                       │
│  Netflix       Monthly  ₹649    Next: May 3                     │
│  Spotify       Annual   ₹1,189  Next: Aug 12                    │
│  iCloud        Monthly  ₹75     Next: May 7                     │
│  ...                                                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 15. Testing Strategy

- **Unit tests** for: HDFC PDF parser, HDFC CSV parser, multi-line merger, Indian number parser, date parser, UPI parser, pattern extractor, classifier tiers, NAV parser, transfer pair-matcher, subscription detector, Decimal TypeDecorator.
- **Integration tests** for: import → classify → store flow; ATM split → envelope balance; SIP → holding update.
- **API tests** with `httpx.AsyncClient`.
- **Frontend:** Vitest for utilities; Playwright for one happy-path E2E (import → dashboard renders).
- **Fixture data:** 3 months of synthetic HDFC statements (PDF + CSV) covering edge cases (multi-line narration, UPI, ATM, SIP, IMPS, refund, EMI).

---

## 16. Coding Standards

- **Type hints everywhere.** Python 3.14 has deferred annotation evaluation by default; do not import `from __future__ import annotations` unless needed for circular imports.
- **No floats for money.** Use `decimal.Decimal` always. Custom SQLAlchemy `TypeDecorator` for TEXT↔Decimal conversion.
- **Black + Ruff + mypy --strict** for Python.
- **Prettier + ESLint + TS strict mode** for frontend.
- **One commit per phase.** Each phase boundary = a tagged commit `phase-N-complete`.

---

## 17. Out of Scope (do not build in v1)

- Authentication / user management
- Banks other than HDFC
- LLM-based features of any kind
- Goals & long-term forecasting
- OCR for receipts
- Mobile-responsive design
- Multi-currency
- Credit card statement parsing (treat card bill as single debit for now)
- NSE/BSE stock price feeds (manual entry only)
- Notification system / email digests
- Backup/restore UX (back up the SQLite file manually)

---

## 18. Handoff Instructions for Claude Code

1. Read this entire document before writing any code.
2. Confirm Python 3.14 install + uv available.
3. Build **Phase 1 only**. Run tests. Stop. Wait for review.
4. After approval, proceed to next phase. Never skip ahead.
5. If any spec conflicts with reality discovered during build, **flag it before deviating**. Do not silently change schema or behavior.
6. Use the existing parser handoff document (System 1) as the authoritative source for HDFC parsing details — particularly the multi-line merger algorithm, Indian number parser, and password decryption flow.
7. Every phase ends with: tests green, demo-able UI for new features, commit tagged `phase-N-complete`.

---

**End of plan.**
