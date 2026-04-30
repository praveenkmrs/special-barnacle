import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { PageShell } from "@/components/PageShell";
import { apiGet, type UpcomingSubscription } from "@/lib/api";
import { formatINR } from "@/lib/money";

interface DashboardData {
  period_from: string;
  period_to: string;
  cash_buffer: string;
  capital_deployed_cost: string;
  capital_deployed_value: string;
  net_cashflow: string;
  income: string;
  expenses: string;
  accounts: {
    account_id: number;
    name: string;
    type: string;
    bank_code: string | null;
    envelope_owner: string | null;
    balance: string;
  }[];
  expense_breakdown: {
    category_id: number | null;
    category_name: string | null;
    parent_id: number | null;
    parent_name: string | null;
    is_income: number;
    is_transfer: number;
    debit_total: string;
    credit_total: string;
  }[];
  subscription_run_rate_monthly: string;
  subscription_run_rate_annual: string;
  review_queue_count: number;
}

const WINDOWS: { label: string; days: number }[] = [
  { label: "Last 30 days", days: 30 },
  { label: "Last 90 days", days: 90 },
  { label: "Last 180 days", days: 180 },
  { label: "Last 12 months", days: 365 },
];

function isoMinusDays(d: number): string {
  const dt = new Date();
  dt.setDate(dt.getDate() - d);
  return dt.toISOString().slice(0, 10);
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function Dashboard() {
  const [windowDays, setWindowDays] = useState(90);
  const from = useMemo(() => isoMinusDays(windowDays), [windowDays]);
  const to = todayIso();

  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard", from, to],
    queryFn: () =>
      apiGet<DashboardData>(`/analytics/dashboard?from=${from}&to=${to}`),
  });

  const { data: upcoming = [] } = useQuery({
    queryKey: ["upcoming-30"],
    queryFn: () => apiGet<UpcomingSubscription[]>("/subscriptions/upcoming?days=30"),
  });

  if (isLoading) return <PageShell title="Dashboard"><div>Loading…</div></PageShell>;
  if (error || !data)
    return (
      <PageShell title="Dashboard">
        <div className="text-red-700">Failed to load. Is the API running?</div>
      </PageShell>
    );

  const capCost = data.capital_deployed_cost;
  const capValue = data.capital_deployed_value;
  const gainPct =
    Number(capCost) > 0
      ? ((Number(capValue) - Number(capCost)) / Number(capCost)) * 100
      : 0;

  const expenseGroups = groupByParent(data.expense_breakdown);
  const expensesTotal = data.expense_breakdown.reduce(
    (s, e) => s + Number(e.debit_total),
    0,
  );

  return (
    <PageShell
      title="Dashboard"
      description={`Period ${data.period_from} → ${data.period_to}`}
    >
      <div className="mb-4 flex items-center gap-2">
        <span className="text-xs text-muted-foreground">Time window:</span>
        <select
          value={windowDays}
          onChange={(e) => setWindowDays(Number(e.target.value))}
          className="rounded border border-border px-2 py-1 text-sm"
        >
          {WINDOWS.map((w) => (
            <option key={w.days} value={w.days}>
              {w.label}
            </option>
          ))}
        </select>
        {data.review_queue_count > 0 && (
          <a
            href="/review"
            className="ml-auto rounded bg-amber-100 px-2 py-1 text-xs text-amber-800 hover:bg-amber-200"
          >
            Review queue: {data.review_queue_count}
          </a>
        )}
      </div>

      <div className="mb-4 grid grid-cols-3 gap-4">
        <Tile label="Cash Buffer" value={formatINR(data.cash_buffer)} sub="bank + envelopes" />
        <Tile
          label="Capital Deployed"
          value={formatINR(capValue)}
          sub={`cost ${formatINR(capCost)} · ${gainPct.toFixed(1)}%`}
          tone={gainPct >= 0 ? "positive" : "negative"}
        />
        <Tile
          label="Net Cashflow"
          value={formatINR(data.net_cashflow)}
          sub={`income ${formatINR(data.income)} · expenses ${formatINR(data.expenses)}`}
          tone={Number(data.net_cashflow) >= 0 ? "positive" : "negative"}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="rounded border border-border bg-white p-4">
          <h3 className="mb-3 text-sm font-semibold">Accounts</h3>
          <table className="w-full text-sm">
            <tbody>
              {data.accounts.map((a) => (
                <tr key={a.account_id} className="border-b border-border/60 last:border-b-0">
                  <td className="py-1.5">
                    <div>{a.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {a.type}
                      {a.envelope_owner ? ` · ${a.envelope_owner}` : ""}
                    </div>
                  </td>
                  <td className="text-right font-mono">{formatINR(a.balance)}</td>
                </tr>
              ))}
              {data.accounts.length === 0 && (
                <tr>
                  <td className="py-2 text-muted-foreground" colSpan={2}>
                    No accounts. <a href="/accounts" className="underline">Add one</a>.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="rounded border border-border bg-white p-4">
          <h3 className="mb-3 text-sm font-semibold">Upcoming (next 30 days)</h3>
          {upcoming.length === 0 ? (
            <div className="text-sm text-muted-foreground">No subscriptions due.</div>
          ) : (
            <table className="w-full text-sm">
              <tbody>
                {upcoming.slice(0, 8).map((u, i) => (
                  <tr key={i} className="border-b border-border/60 last:border-b-0">
                    <td className="py-1.5">
                      <div>{u.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {u.cadence ?? "—"} · due {u.due_date}
                      </div>
                    </td>
                    <td className="text-right font-mono">
                      {u.amount ? formatINR(u.amount) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="mt-3 border-t border-border pt-2 text-xs text-muted-foreground">
            Run-rate: monthly {formatINR(data.subscription_run_rate_monthly)} · annual{" "}
            {formatINR(data.subscription_run_rate_annual)}
          </div>
        </div>
      </div>

      <div className="mt-4 rounded border border-border bg-white p-4">
        <h3 className="mb-3 text-sm font-semibold">
          Expenses by category — total {formatINR(String(expensesTotal))}
        </h3>
        {expenseGroups.length === 0 ? (
          <div className="text-sm text-muted-foreground">
            No expense data in this window. Import a statement and classify.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-muted-foreground">
              <tr>
                <th className="py-1.5">Category</th>
                <th className="text-right">Amount</th>
                <th className="text-right">Share</th>
              </tr>
            </thead>
            <tbody>
              {expenseGroups.map((g) => (
                <tr key={g.parent_name ?? "Uncategorised"} className="border-t border-border">
                  <td className="py-1.5">{g.parent_name ?? "Uncategorised"}</td>
                  <td className="text-right font-mono">{formatINR(String(g.total))}</td>
                  <td className="text-right text-xs text-muted-foreground">
                    {expensesTotal > 0
                      ? `${((g.total / expensesTotal) * 100).toFixed(1)}%`
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </PageShell>
  );
}

function groupByParent(
  rows: DashboardData["expense_breakdown"],
): { parent_name: string | null; total: number }[] {
  const m = new Map<string, number>();
  for (const r of rows) {
    const key = r.parent_name ?? r.category_name ?? "Uncategorised";
    m.set(key, (m.get(key) ?? 0) + Number(r.debit_total));
  }
  return Array.from(m.entries())
    .map(([parent_name, total]) => ({ parent_name, total }))
    .sort((a, b) => b.total - a.total);
}

function Tile({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "positive" | "negative";
}) {
  return (
    <div className="rounded-md border border-border bg-white p-4">
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div
        className={
          "mt-2 font-mono text-2xl font-semibold " +
          (tone === "positive"
            ? "text-emerald-700"
            : tone === "negative"
              ? "text-red-700"
              : "")
        }
      >
        {value}
      </div>
      {sub && <div className="mt-1 text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}
