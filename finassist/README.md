# FinAssist

Local-first personal finance assistant. Indian banking context, HDFC-only in v1.

Track balances across bank accounts, credit cards, cash envelopes (Mom/Wife/Daughter/etc.), and
investments. Imports HDFC PDF/CSV statements, classifies transactions through a 3-tier rule
engine + TF-IDF fuzzy fallback, detects subscriptions and inter-account transfers, and shows
everything on a dashboard with Cash Buffer / Capital Deployed / Net Cashflow.

## Features (v1)

- HDFC PDF (encrypted) + CSV statement upload with multi-line narration handling
- 3-tier duplicate detector — never silently drops legitimate same-day same-amount transactions
- 3-tier classifier (active rules → candidate rules → TF-IDF fuzzy) with auto-promotion
- Cash envelope accounts with ATM-split UX and manual cash spend logging
- Auto-detected monthly/quarterly/annual subscriptions with 12-month projections
- AMFI NAV scheduler (daily 23:30 IST) for mutual fund holdings; SIP debits link to holdings
- Transfer pair-matcher (debit/credit across accounts within 72h)
- Dashboard with time-window selector, expense breakdown by parent category, account balances,
  upcoming subscriptions, review-queue badge
- Per-entity CSV export (transactions, accounts, categories, rules, subscriptions, holdings,
  imports, nav_cache)

## Quick start (dev, without Docker)

Requires Python 3.14, [uv](https://github.com/astral-sh/uv), Node 22.

```bash
# Backend
cd finassist
uv sync --extra dev
uv run uvicorn api.main:app --reload --host 127.0.0.1 --port 8000

# Frontend (separate terminal)
cd finassist/web
npm install
npm run dev
```

API on http://127.0.0.1:8000 (with /docs OpenAPI), web on http://127.0.0.1:5173.

The web dev server proxies `/api/*` to the backend on port 8000 (see `vite.config.ts`).

## Docker

```bash
cd finassist
docker compose up --build
```

API on http://127.0.0.1:8000, web on http://127.0.0.1:8080. SQLite DB lives in the
`finassist-data` volume (mounted at `/data/finassist.db` inside the container).

## First-time setup flow

1. Open http://127.0.0.1:5173/accounts and create:
   - One **bank** account for HDFC (`type=bank`, `bank_code=HDFC`).
   - Optionally **cash_envelope** accounts for family members.
2. Open `/imports` and upload an HDFC statement (PDF or CSV).
   - For encrypted PDFs, enter your 9-digit Customer ID as the password.
3. Visit `/review` to triage classification suggestions and resolve duplicate groups.
4. Tier-1 rules can be added directly under `/rules`; manually classifying a transaction
   auto-creates candidate rules that get promoted after 5 hits or 30 days.
5. Run subscription auto-detect via the button on `/subscriptions` after a few months of imports.
6. Add `mf` or `broker` accounts under `/accounts`, then create holdings under `/holdings`. Click
   "Refresh NAV" to fetch from AMFI.

## Tests

```bash
cd finassist
uv run pytest                 # all backend tests
cd web && npx tsc --noEmit    # frontend typecheck
```

## Project layout

```
finassist/
├── api/                # FastAPI app
├── core/               # Business logic
│   ├── analytics/      # Dashboard aggregations + balances
│   ├── banks/          # BankAdapter ABC + HDFC implementation
│   ├── classifier/     # Tier 1/2/3 + pattern extractor + promoter
│   ├── envelopes/      # Cash envelope split + manual debit
│   ├── imports/        # 3-tier duplicate detector + import service
│   ├── investments/    # AMFI NAV fetcher + holdings service
│   ├── parsing/        # Indian amount/date/UPI parsers + RawTransaction
│   ├── subscriptions/  # Auto-detector + linker
│   └── transfers/      # Pair matcher
├── db/                 # SQLAlchemy models, types (DecimalText), seeds, migrations
├── tests/              # pytest-asyncio, no real network calls
└── web/                # React 18 + Vite + Tailwind + TanStack Query + Tremor
```

## Plan documents

See `documents/finassist-v1-plan.md` for the master plan and `documents/HANDOFF.md` for HDFC
parser specifics.

## Out of scope (v1)

Auth, banks other than HDFC, LLM features, goals/forecasting, OCR, mobile UI, multi-currency,
credit-card statement line-by-line parsing, NSE/BSE feeds, notifications, automated
backup/restore.
