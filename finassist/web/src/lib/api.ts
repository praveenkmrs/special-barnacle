const BASE = "/api";

export async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) throw new Error(`GET ${path} failed: ${r.status}`);
  return r.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(`POST ${path} ${r.status}: ${text}`);
  }
  return r.json() as Promise<T>;
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(`PATCH ${path} ${r.status}: ${text}`);
  }
  return r.json() as Promise<T>;
}

export async function apiPostForm<T>(path: string, form: FormData): Promise<T> {
  const r = await fetch(`${BASE}${path}`, { method: "POST", body: form });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(`POST ${path} ${r.status}: ${text}`);
  }
  return r.json() as Promise<T>;
}

export interface Account {
  id: number;
  name: string;
  type: string;
  bank_code: string | null;
  account_number_masked: string | null;
  envelope_owner: string | null;
  currency: string;
  is_active: number;
  opening_balance: string;
  opening_balance_date: string | null;
}

export interface Transaction {
  id: number;
  account_id: number;
  txn_date: string;
  amount: string;
  type: "debit" | "credit";
  narration: string;
  balance_after: string | null;
  reference: string | null;
  category_id: number | null;
  subscription_id: number | null;
  is_transfer: number;
  classification_source: string | null;
  classification_confidence: number | null;
  needs_review: number;
  review_reason: string | null;
  dup_group_id: number | null;
  notes: string | null;
  source_file: string | null;
}

export interface Category {
  id: number;
  name: string;
  parent_id: number | null;
  is_transfer: number;
  is_income: number;
  display_order: number | null;
}

export interface Rule {
  id: number;
  pattern: string;
  pattern_type: string | null;
  amount_min: string | null;
  amount_max: string | null;
  account_id: number | null;
  txn_type: string | null;
  category_id: number | null;
  subscription_id: number | null;
  status: string;
  priority: number;
  hit_count: number;
  conflict_count: number;
  last_hit_at: string | null;
  created_by: string;
  created_at: string;
  promoted_at: string | null;
  blacklist_until: string | null;
}

export interface ImportRecord {
  id: number;
  account_id: number;
  source_file: string | null;
  source_format: string | null;
  bank_code: string | null;
  period_start: string | null;
  period_end: string | null;
  rows_imported: number;
  rows_duplicate: number;
  rows_failed: number;
  status: string | null;
  error_log: string | null;
}

export interface ImportResult {
  import_id: number;
  rows_imported: number;
  rows_duplicate: number;
  rows_ambiguous: number;
  rows_failed: number;
  period_start: string | null;
  period_end: string | null;
  status: string;
  error_log: string | null;
}

export interface DupGroupRow {
  id: number;
  account_id: number;
  txn_date: string;
  amount: string;
  type: "debit" | "credit";
  narration: string;
  balance_after: string | null;
  reference: string | null;
  source_file: string | null;
  source_page: number | null;
}

export interface DupGroup {
  group_id: number;
  rows: DupGroupRow[];
}

export interface TransferTxn {
  id: number;
  account_id: number;
  txn_date: string;
  amount: string;
  type: "debit" | "credit";
  narration: string;
  reference: string | null;
  transfer_pair_id: number | null;
}

export interface TransferCandidate {
  debit: TransferTxn;
  credit: TransferTxn;
}

export interface Subscription {
  id: number;
  name: string;
  expected_amount: string | null;
  amount_tolerance_pct: number;
  cadence: string | null;
  next_expected_date: string | null;
  status: string;
  category_id: number | null;
  account_id: number | null;
  started_on: string | null;
  ended_on: string | null;
  notes: string | null;
  auto_detected: number;
  monthly_run_rate: string;
  annual_run_rate: string;
}

export interface UpcomingSubscription {
  subscription_id: number;
  name: string;
  due_date: string;
  amount: string | null;
  cadence: string | null;
}

export interface SubscriptionTxn {
  id: number;
  account_id: number;
  txn_date: string;
  amount: string;
  type: "debit" | "credit";
  narration: string;
  category_id: number | null;
}

export interface Holding {
  id: number;
  account_id: number;
  instrument_type: string;
  identifier: string;
  name: string;
  units: string;
  avg_cost: string | null;
  total_invested: string;
  current_nav: string | null;
  current_value: string | null;
  nav_updated_at: string | null;
  gain: string | null;
  gain_pct: number | null;
}

export interface HoldingTxn {
  id: number;
  holding_id: number;
  txn_date: string;
  type: "buy" | "sell" | "dividend" | "split" | "bonus";
  units: string;
  price_per_unit: string | null;
  amount: string;
  linked_transaction_id: number | null;
  notes: string | null;
}

export interface RefreshNavResult {
  nav_rows_updated: number;
  holdings_revalued: number;
}
