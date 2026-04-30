import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { PageShell } from "@/components/PageShell";
import { apiGet, type Account, type Category, type Transaction } from "@/lib/api";
import { formatINR } from "@/lib/money";

export function Transactions() {
  const [accountId, setAccountId] = useState<number | "">("");
  const [needsReview, setNeedsReview] = useState<"" | "0" | "1">("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

  const { data: accounts = [] } = useQuery({
    queryKey: ["accounts"],
    queryFn: () => apiGet<Account[]>("/accounts"),
  });
  const { data: categories = [] } = useQuery({
    queryKey: ["categories"],
    queryFn: () => apiGet<Category[]>("/categories"),
  });

  const queryString = useMemo(() => {
    const q = new URLSearchParams();
    if (accountId !== "") q.set("account_id", String(accountId));
    if (needsReview !== "") q.set("needs_review", needsReview);
    if (fromDate) q.set("from", fromDate);
    if (toDate) q.set("to", toDate);
    q.set("limit", "300");
    return q.toString();
  }, [accountId, needsReview, fromDate, toDate]);

  const { data: txns = [], isLoading } = useQuery({
    queryKey: ["transactions", queryString],
    queryFn: () => apiGet<Transaction[]>(`/transactions?${queryString}`),
  });

  const accountName = (id: number) =>
    accounts.find((a) => a.id === id)?.name ?? `#${id}`;
  const categoryName = (id: number | null) =>
    id == null ? "—" : categories.find((c) => c.id === id)?.name ?? `#${id}`;

  return (
    <PageShell title="Transactions" description="Filter by account, date, review state.">
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <Field label="Account">
          <select
            value={accountId}
            onChange={(e) =>
              setAccountId(e.target.value === "" ? "" : Number(e.target.value))
            }
            className="rounded border border-border px-2 py-1 text-sm"
          >
            <option value="">All</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Review">
          <select
            value={needsReview}
            onChange={(e) => setNeedsReview(e.target.value as "" | "0" | "1")}
            className="rounded border border-border px-2 py-1 text-sm"
          >
            <option value="">Any</option>
            <option value="1">Needs review</option>
            <option value="0">Cleared</option>
          </select>
        </Field>
        <Field label="From">
          <input
            type="date"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            className="rounded border border-border px-2 py-1 text-sm"
          />
        </Field>
        <Field label="To">
          <input
            type="date"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            className="rounded border border-border px-2 py-1 text-sm"
          />
        </Field>
      </div>

      {isLoading ? (
        <div>Loading…</div>
      ) : txns.length === 0 ? (
        <div className="text-sm text-muted-foreground">No transactions.</div>
      ) : (
        <table className="w-full text-sm">
          <thead className="text-left text-muted-foreground">
            <tr>
              <th className="py-2">Date</th>
              <th>Account</th>
              <th>Narration</th>
              <th>Category</th>
              <th className="text-right">Amount</th>
              <th>Type</th>
              <th>Flags</th>
            </tr>
          </thead>
          <tbody>
            {txns.map((t) => (
              <tr key={t.id} className="border-t border-border align-top">
                <td className="py-2">{t.txn_date}</td>
                <td>{accountName(t.account_id)}</td>
                <td className="max-w-md truncate" title={t.narration}>
                  {t.narration}
                </td>
                <td>{categoryName(t.category_id)}</td>
                <td className="text-right font-mono">{formatINR(t.amount)}</td>
                <td>
                  <span
                    className={
                      t.type === "credit"
                        ? "text-emerald-700"
                        : "text-red-600"
                    }
                  >
                    {t.type}
                  </span>
                </td>
                <td className="space-x-1 text-xs">
                  {t.needs_review === 1 && (
                    <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-800">
                      review
                    </span>
                  )}
                  {t.dup_group_id != null && (
                    <span className="rounded bg-purple-100 px-1.5 py-0.5 text-purple-800">
                      dup#{t.dup_group_id}
                    </span>
                  )}
                  {t.is_transfer === 1 && (
                    <span className="rounded bg-blue-100 px-1.5 py-0.5 text-blue-800">
                      transfer
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </PageShell>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs text-muted-foreground">{label}</label>
      {children}
    </div>
  );
}
