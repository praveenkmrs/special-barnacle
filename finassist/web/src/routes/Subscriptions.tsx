import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { PageShell } from "@/components/PageShell";
import {
  apiGet,
  apiPost,
  type Account,
  type Subscription,
  type SubscriptionTxn,
  type UpcomingSubscription,
} from "@/lib/api";

export function Subscriptions() {
  const qc = useQueryClient();
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const { data: subs = [], isLoading } = useQuery({
    queryKey: ["subscriptions"],
    queryFn: () => apiGet<Subscription[]>("/subscriptions"),
  });
  const { data: accounts = [] } = useQuery({
    queryKey: ["accounts"],
    queryFn: () => apiGet<Account[]>("/accounts"),
  });
  const { data: upcoming = [] } = useQuery({
    queryKey: ["subscriptions", "upcoming"],
    queryFn: () => apiGet<UpcomingSubscription[]>("/subscriptions/upcoming?days=30"),
  });

  const detect = useMutation({
    mutationFn: () => apiPost<{ detected: number }>("/subscriptions/detect", {}),
    onSuccess: (res) => {
      setToast(`Detected ${res.detected} subscription(s)`);
      qc.invalidateQueries({ queryKey: ["subscriptions"] });
    },
    onError: (e: Error) => setToast(`Detect failed: ${e.message}`),
  });

  const [name, setName] = useState("");
  const [expectedAmount, setExpectedAmount] = useState("");
  const [cadence, setCadence] = useState("monthly");
  const [accountId, setAccountId] = useState<number | "">("");
  const [nextDate, setNextDate] = useState("");

  const create = useMutation({
    mutationFn: () =>
      apiPost<Subscription>("/subscriptions", {
        name,
        expected_amount: expectedAmount === "" ? null : expectedAmount,
        cadence,
        account_id: accountId === "" ? null : accountId,
        next_expected_date: nextDate === "" ? null : nextDate,
        status: "active",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["subscriptions"] });
      setName("");
      setExpectedAmount("");
      setNextDate("");
    },
  });

  const annualRunRate = subs
    .filter((s) => s.status === "active")
    .reduce((sum, s) => sum + Number(s.annual_run_rate || 0), 0);

  return (
    <PageShell title="Subscriptions" description="Auto-detected and manual recurring payments.">
      {toast && (
        <div className="mb-3 rounded border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          {toast}
        </div>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-4 rounded border border-border bg-muted/30 p-3">
        <div>
          <div className="text-xs uppercase text-muted-foreground">Annual run-rate</div>
          <div className="text-2xl font-semibold">
            ₹{annualRunRate.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
          </div>
        </div>
        <div className="ml-auto">
          <button
            onClick={() => detect.mutate()}
            disabled={detect.isPending}
            className="rounded bg-primary px-3 py-1.5 text-sm text-primary-foreground"
          >
            Run auto-detect now
          </button>
        </div>
      </div>

      <form
        className="mb-4 flex flex-wrap items-end gap-3 rounded border border-border p-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (!name) return;
          create.mutate();
        }}
      >
        <div>
          <label className="block text-xs text-muted-foreground">Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="rounded border border-border px-2 py-1 text-sm"
            placeholder="Netflix"
          />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground">Expected amount</label>
          <input
            value={expectedAmount}
            onChange={(e) => setExpectedAmount(e.target.value)}
            className="w-28 rounded border border-border px-2 py-1 text-sm"
            placeholder="649"
          />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground">Cadence</label>
          <select
            value={cadence}
            onChange={(e) => setCadence(e.target.value)}
            className="rounded border border-border px-2 py-1 text-sm"
          >
            <option value="monthly">monthly</option>
            <option value="quarterly">quarterly</option>
            <option value="annual">annual</option>
            <option value="custom">custom</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-muted-foreground">Account</label>
          <select
            value={accountId}
            onChange={(e) => setAccountId(e.target.value === "" ? "" : Number(e.target.value))}
            className="rounded border border-border px-2 py-1 text-sm"
          >
            <option value="">—</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-muted-foreground">Next due</label>
          <input
            type="date"
            value={nextDate}
            onChange={(e) => setNextDate(e.target.value)}
            className="rounded border border-border px-2 py-1 text-sm"
          />
        </div>
        <button
          type="submit"
          className="rounded bg-primary px-3 py-1.5 text-sm text-primary-foreground"
          disabled={create.isPending}
        >
          Add subscription
        </button>
      </form>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <h3 className="mb-2 text-sm font-semibold">Active subscriptions</h3>
          {isLoading ? (
            <div>Loading…</div>
          ) : subs.length === 0 ? (
            <div className="text-sm text-muted-foreground">No subscriptions yet.</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="text-left text-muted-foreground">
                <tr>
                  <th className="py-2">Name</th>
                  <th>Amount</th>
                  <th>Cadence</th>
                  <th>Next due</th>
                  <th>Status</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {subs.map((s) => (
                  <SubRow
                    key={s.id}
                    sub={s}
                    expanded={expandedId === s.id}
                    onClick={() => setExpandedId(expandedId === s.id ? null : s.id)}
                  />
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div>
          <h3 className="mb-2 text-sm font-semibold">Upcoming (next 30 days)</h3>
          {upcoming.length === 0 ? (
            <div className="text-sm text-muted-foreground">Nothing due.</div>
          ) : (
            <ul className="space-y-1 text-sm">
              {upcoming.map((u, i) => (
                <li
                  key={`${u.subscription_id}-${u.due_date}-${i}`}
                  className="flex items-center justify-between rounded border border-border px-2 py-1"
                >
                  <span>{u.name}</span>
                  <span className="text-muted-foreground">
                    {u.due_date} · ₹{u.amount ?? "—"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </PageShell>
  );
}

function SubRow({
  sub,
  expanded,
  onClick,
}: {
  sub: Subscription;
  expanded: boolean;
  onClick: () => void;
}) {
  const { data: txns = [] } = useQuery({
    queryKey: ["subscriptions", sub.id, "transactions"],
    queryFn: () => apiGet<SubscriptionTxn[]>(`/subscriptions/${sub.id}/transactions`),
    enabled: expanded,
  });
  return (
    <>
      <tr
        className="cursor-pointer border-t border-border hover:bg-muted/30"
        onClick={onClick}
      >
        <td className="py-2 font-medium">{sub.name}</td>
        <td>₹{sub.expected_amount ?? "—"}</td>
        <td>{sub.cadence ?? "—"}</td>
        <td>{sub.next_expected_date ?? "—"}</td>
        <td>
          <span className="rounded bg-muted px-2 py-0.5 text-xs">{sub.status}</span>
        </td>
        <td className="text-xs text-muted-foreground">
          {sub.auto_detected ? "auto" : "manual"}
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={6} className="bg-muted/20 px-3 py-2">
            <div className="text-xs font-semibold text-muted-foreground">Linked transactions</div>
            {txns.length === 0 ? (
              <div className="text-sm text-muted-foreground">None linked.</div>
            ) : (
              <table className="w-full text-xs">
                <tbody>
                  {txns.map((t) => (
                    <tr key={t.id} className="border-t border-border">
                      <td className="py-1">{t.txn_date}</td>
                      <td>₹{t.amount}</td>
                      <td className="truncate">{t.narration}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
