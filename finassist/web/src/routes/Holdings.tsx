import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import Decimal from "decimal.js";
import { PageShell } from "@/components/PageShell";
import {
  apiGet,
  apiPost,
  type Account,
  type Holding,
  type RefreshNavResult,
} from "@/lib/api";
import { formatINR } from "@/lib/money";

export function Holdings() {
  const qc = useQueryClient();

  const { data: holdings = [], isLoading } = useQuery({
    queryKey: ["holdings"],
    queryFn: () => apiGet<Holding[]>("/holdings"),
  });
  const { data: accounts = [] } = useQuery({
    queryKey: ["accounts"],
    queryFn: () => apiGet<Account[]>("/accounts"),
  });

  const investmentAccounts = useMemo(
    () => accounts.filter((a) => ["mf", "broker", "epf", "nps"].includes(a.type)),
    [accounts],
  );

  const [accountId, setAccountId] = useState<string>("");
  const [identifier, setIdentifier] = useState("");
  const [name, setName] = useState("");
  const [instrumentType, setInstrumentType] = useState("mf");

  const create = useMutation({
    mutationFn: () =>
      apiPost<Holding>("/holdings", {
        account_id: Number(accountId),
        instrument_type: instrumentType,
        identifier,
        name,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["holdings"] });
      setIdentifier("");
      setName("");
    },
  });

  const refresh = useMutation({
    mutationFn: () => apiPost<RefreshNavResult>("/holdings/refresh-nav", {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["holdings"] }),
  });

  const totals = useMemo(() => {
    let invested = new Decimal(0);
    let current = new Decimal(0);
    for (const h of holdings) {
      invested = invested.plus(h.total_invested || 0);
      if (h.current_value != null) current = current.plus(h.current_value);
    }
    return { invested: invested.toString(), current: current.toString() };
  }, [holdings]);

  return (
    <PageShell
      title="Holdings"
      description="Mutual funds, stocks, FDs — capital deployed and current value."
    >
      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <div className="rounded border border-border p-3">
          <div className="text-xs text-muted-foreground">Capital Deployed</div>
          <div className="font-mono text-lg">{formatINR(totals.invested)}</div>
        </div>
        <div className="rounded border border-border p-3">
          <div className="text-xs text-muted-foreground">Current Value</div>
          <div className="font-mono text-lg">{formatINR(totals.current)}</div>
        </div>
        <div className="rounded border border-border p-3 flex items-center justify-between">
          <div>
            <div className="text-xs text-muted-foreground">NAV</div>
            <div className="text-sm">
              {refresh.data
                ? `${refresh.data.nav_rows_updated} rows / ${refresh.data.holdings_revalued} holdings`
                : "—"}
            </div>
          </div>
          <button
            type="button"
            className="rounded bg-primary px-3 py-1.5 text-sm text-primary-foreground"
            disabled={refresh.isPending}
            onClick={() => refresh.mutate()}
          >
            {refresh.isPending ? "Refreshing…" : "Refresh NAV"}
          </button>
        </div>
      </div>

      {refresh.error && (
        <div className="mb-4 text-xs text-red-600">
          {(refresh.error as Error).message}
        </div>
      )}

      <form
        className="mb-6 flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (!accountId || !identifier || !name) return;
          create.mutate();
        }}
      >
        <div>
          <label className="block text-xs text-muted-foreground">Account</label>
          <select
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
            className="rounded border border-border px-2 py-1 text-sm"
          >
            <option value="">Select…</option>
            {investmentAccounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name} ({a.type})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-muted-foreground">Type</label>
          <select
            value={instrumentType}
            onChange={(e) => setInstrumentType(e.target.value)}
            className="rounded border border-border px-2 py-1 text-sm"
          >
            <option value="mf">mf</option>
            <option value="stock">stock</option>
            <option value="fd">fd</option>
            <option value="epf">epf</option>
            <option value="nps">nps</option>
            <option value="crypto">crypto</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-muted-foreground">
            Scheme code / Symbol
          </label>
          <input
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            className="rounded border border-border px-2 py-1 text-sm"
            placeholder="119551"
          />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground">Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="rounded border border-border px-2 py-1 text-sm"
            placeholder="ABSL Frontline Equity"
          />
        </div>
        <button
          type="submit"
          className="rounded bg-primary px-3 py-1.5 text-sm text-primary-foreground"
          disabled={create.isPending}
        >
          {create.isPending ? "…" : "Add holding"}
        </button>
        {create.error && (
          <span className="text-xs text-red-600">
            {(create.error as Error).message}
          </span>
        )}
      </form>

      {isLoading ? (
        <div>Loading…</div>
      ) : (
        <table className="w-full text-sm">
          <thead className="text-left text-muted-foreground">
            <tr>
              <th className="py-2">Name</th>
              <th>Type</th>
              <th className="text-right">Units</th>
              <th className="text-right">Avg cost</th>
              <th className="text-right">Current NAV</th>
              <th className="text-right">Invested</th>
              <th className="text-right">Value</th>
              <th className="text-right">Gain</th>
              <th className="text-right">Gain %</th>
            </tr>
          </thead>
          <tbody>
            {holdings.map((h) => {
              const gainNum = h.gain ? new Decimal(h.gain) : null;
              const cls =
                gainNum && gainNum.isPositive()
                  ? "text-emerald-600"
                  : gainNum && gainNum.isNegative()
                    ? "text-red-600"
                    : "";
              return (
                <tr key={h.id} className="border-t border-border">
                  <td className="py-2">{h.name}</td>
                  <td>{h.instrument_type}</td>
                  <td className="text-right font-mono">{h.units}</td>
                  <td className="text-right font-mono">
                    {h.avg_cost ? formatINR(h.avg_cost) : "—"}
                  </td>
                  <td className="text-right font-mono">
                    {h.current_nav ? formatINR(h.current_nav) : "—"}
                  </td>
                  <td className="text-right font-mono">
                    {formatINR(h.total_invested)}
                  </td>
                  <td className="text-right font-mono">
                    {h.current_value ? formatINR(h.current_value) : "—"}
                  </td>
                  <td className={`text-right font-mono ${cls}`}>
                    {h.gain ? formatINR(h.gain) : "—"}
                  </td>
                  <td className={`text-right font-mono ${cls}`}>
                    {h.gain_pct != null ? `${h.gain_pct.toFixed(2)}%` : "—"}
                  </td>
                </tr>
              );
            })}
            {holdings.length === 0 && (
              <tr>
                <td colSpan={9} className="py-4 text-center text-muted-foreground">
                  No holdings yet — add one above.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </PageShell>
  );
}
