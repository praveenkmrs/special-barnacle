import { Card } from "@tremor/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { PageShell } from "@/components/PageShell";
import {
  apiGet,
  apiPost,
  type Account,
  type Category,
  type Transaction,
} from "@/lib/api";
import { formatINR } from "@/lib/money";

interface Envelope {
  id: number;
  name: string;
  envelope_owner: string | null;
  balance: string;
}

const ATM_RX = /\b(ATW|NWD|CASH WDL|ATM)\b/i;

export function Envelopes() {
  const qc = useQueryClient();

  const { data: envelopes = [], isLoading: envLoading } = useQuery({
    queryKey: ["envelopes"],
    queryFn: () => apiGet<Envelope[]>("/envelopes"),
  });

  const { data: accounts = [] } = useQuery({
    queryKey: ["accounts"],
    queryFn: () => apiGet<Account[]>("/accounts"),
  });

  const { data: categories = [] } = useQuery({
    queryKey: ["categories"],
    queryFn: () => apiGet<Category[]>("/categories"),
  });

  const bankAccounts = useMemo(
    () => accounts.filter((a) => a.type === "bank"),
    [accounts]
  );

  // Manual debit form state
  const [debitAcc, setDebitAcc] = useState<number | "">("");
  const [debitDate, setDebitDate] = useState<string>(
    new Date().toISOString().slice(0, 10)
  );
  const [debitAmount, setDebitAmount] = useState<string>("");
  const [debitNarration, setDebitNarration] = useState<string>("");
  const [debitCategory, setDebitCategory] = useState<number | "">("");

  const debitMutation = useMutation({
    mutationFn: async () => {
      if (debitAcc === "" || debitCategory === "") {
        throw new Error("Account and category required");
      }
      return apiPost(`/envelopes/${debitAcc}/debit`, {
        txn_date: debitDate,
        amount: debitAmount,
        narration: debitNarration,
        category_id: debitCategory,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["envelopes"] });
      qc.invalidateQueries({ queryKey: ["transactions"] });
      setDebitAmount("");
      setDebitNarration("");
    },
  });

  // Bank account selector for ATM withdrawals
  const [bankAcc, setBankAcc] = useState<number | "">("");
  const bankAccQuery = useMemo(() => {
    if (bankAcc === "") return null;
    const q = new URLSearchParams();
    q.set("account_id", String(bankAcc));
    q.set("is_transfer", "0");
    q.set("limit", "200");
    return q.toString();
  }, [bankAcc]);

  const { data: bankTxns = [] } = useQuery({
    queryKey: ["txns-for-atm", bankAccQuery],
    queryFn: () => apiGet<Transaction[]>(`/transactions?${bankAccQuery}`),
    enabled: bankAccQuery !== null,
  });

  const atmWithdrawals = useMemo(
    () =>
      bankTxns.filter(
        (t) => t.type === "debit" && t.is_transfer === 0 && ATM_RX.test(t.narration)
      ),
    [bankTxns]
  );

  // Split modal state
  const [splitTxn, setSplitTxn] = useState<Transaction | null>(null);
  const [splitAmounts, setSplitAmounts] = useState<Record<number, string>>({});

  const openSplitModal = (txn: Transaction) => {
    setSplitTxn(txn);
    const init: Record<number, string> = {};
    envelopes.forEach((e) => {
      init[e.id] = "";
    });
    setSplitAmounts(init);
  };
  const closeSplitModal = () => {
    setSplitTxn(null);
    setSplitAmounts({});
  };

  const splitMutation = useMutation({
    mutationFn: async () => {
      if (!splitTxn) throw new Error("No txn selected");
      const splits = Object.entries(splitAmounts)
        .filter(([, v]) => v.trim() !== "" && Number(v) > 0)
        .map(([accId, v]) => ({
          account_id: Number(accId),
          amount: v,
        }));
      if (splits.length === 0) throw new Error("Allocate at least one split");
      return apiPost("/envelopes/split", {
        parent_txn_id: splitTxn.id,
        splits,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["envelopes"] });
      qc.invalidateQueries({ queryKey: ["txns-for-atm"] });
      qc.invalidateQueries({ queryKey: ["transactions"] });
      closeSplitModal();
    },
  });

  const splitTotal = useMemo(
    () =>
      Object.values(splitAmounts).reduce(
        (sum, v) => sum + (Number(v) || 0),
        0
      ),
    [splitAmounts]
  );

  return (
    <PageShell
      title="Envelopes"
      description="Cash envelopes — track who is holding cash, log spends, split ATM withdrawals."
    >
      <div className="space-y-6">
        <section>
          <h2 className="mb-2 text-sm font-medium text-muted-foreground">
            Envelope balances
          </h2>
          {envLoading ? (
            <div>Loading…</div>
          ) : envelopes.length === 0 ? (
            <div className="text-sm text-muted-foreground">
              No cash envelopes yet — create them via the Accounts page (type =
              cash_envelope).
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
              {envelopes.map((e) => (
                <Card key={e.id}>
                  <div className="text-xs text-muted-foreground">
                    {e.envelope_owner ?? "Envelope"}
                  </div>
                  <div className="text-base font-medium">{e.name}</div>
                  <div className="mt-2 font-mono text-lg">
                    {formatINR(e.balance)}
                  </div>
                </Card>
              ))}
            </div>
          )}
        </section>

        <section>
          <h2 className="mb-2 text-sm font-medium text-muted-foreground">
            Log a manual cash spend
          </h2>
          <Card>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-5">
              <Field label="Envelope">
                <select
                  value={debitAcc}
                  onChange={(e) =>
                    setDebitAcc(e.target.value === "" ? "" : Number(e.target.value))
                  }
                  className="w-full rounded border border-border px-2 py-1 text-sm"
                >
                  <option value="">Pick…</option>
                  {envelopes.map((e) => (
                    <option key={e.id} value={e.id}>
                      {e.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Date">
                <input
                  type="date"
                  value={debitDate}
                  onChange={(e) => setDebitDate(e.target.value)}
                  className="w-full rounded border border-border px-2 py-1 text-sm"
                />
              </Field>
              <Field label="Amount">
                <input
                  type="number"
                  step="0.01"
                  value={debitAmount}
                  onChange={(e) => setDebitAmount(e.target.value)}
                  className="w-full rounded border border-border px-2 py-1 text-sm"
                />
              </Field>
              <Field label="Narration">
                <input
                  type="text"
                  value={debitNarration}
                  onChange={(e) => setDebitNarration(e.target.value)}
                  className="w-full rounded border border-border px-2 py-1 text-sm"
                />
              </Field>
              <Field label="Category">
                <select
                  value={debitCategory}
                  onChange={(e) =>
                    setDebitCategory(
                      e.target.value === "" ? "" : Number(e.target.value)
                    )
                  }
                  className="w-full rounded border border-border px-2 py-1 text-sm"
                >
                  <option value="">Pick…</option>
                  {categories
                    .filter((c) => c.parent_id !== null)
                    .map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                </select>
              </Field>
            </div>
            <div className="mt-3 flex items-center gap-3">
              <button
                onClick={() => debitMutation.mutate()}
                disabled={debitMutation.isPending}
                className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
              >
                {debitMutation.isPending ? "Saving…" : "Log spend"}
              </button>
              {debitMutation.isError && (
                <span className="text-xs text-red-600">
                  {(debitMutation.error as Error).message}
                </span>
              )}
              {debitMutation.isSuccess && (
                <span className="text-xs text-emerald-700">Saved.</span>
              )}
            </div>
          </Card>
        </section>

        <section>
          <h2 className="mb-2 text-sm font-medium text-muted-foreground">
            Recent ATM withdrawals to split
          </h2>
          <Card>
            <div className="mb-3">
              <Field label="Bank account">
                <select
                  value={bankAcc}
                  onChange={(e) =>
                    setBankAcc(e.target.value === "" ? "" : Number(e.target.value))
                  }
                  className="rounded border border-border px-2 py-1 text-sm"
                >
                  <option value="">Pick…</option>
                  {bankAccounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            {bankAcc === "" ? (
              <div className="text-sm text-muted-foreground">
                Pick a bank account to find ATM withdrawals.
              </div>
            ) : atmWithdrawals.length === 0 ? (
              <div className="text-sm text-muted-foreground">
                No unsplit ATM withdrawals on this account.
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead className="text-left text-muted-foreground">
                  <tr>
                    <th className="py-2">Date</th>
                    <th>Narration</th>
                    <th className="text-right">Amount</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {atmWithdrawals.map((t) => (
                    <tr key={t.id} className="border-t border-border">
                      <td className="py-2">{t.txn_date}</td>
                      <td className="max-w-md truncate" title={t.narration}>
                        {t.narration}
                      </td>
                      <td className="text-right font-mono">
                        {formatINR(t.amount)}
                      </td>
                      <td className="text-right">
                        <button
                          onClick={() => openSplitModal(t)}
                          className="rounded border border-border px-2 py-1 text-xs hover:bg-slate-50"
                        >
                          Split
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </section>
      </div>

      {splitTxn && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl">
            <h3 className="mb-1 text-lg font-semibold">Split ATM withdrawal</h3>
            <p className="mb-4 text-xs text-muted-foreground">
              {splitTxn.txn_date} · {formatINR(splitTxn.amount)} ·{" "}
              {splitTxn.narration}
            </p>

            <div className="space-y-2">
              {envelopes.map((e) => (
                <div key={e.id} className="flex items-center gap-2">
                  <label className="flex-1 text-sm">
                    {e.name}
                    <span className="ml-1 text-xs text-muted-foreground">
                      (bal {formatINR(e.balance)})
                    </span>
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    placeholder="0"
                    value={splitAmounts[e.id] ?? ""}
                    onChange={(ev) =>
                      setSplitAmounts((prev) => ({
                        ...prev,
                        [e.id]: ev.target.value,
                      }))
                    }
                    className="w-32 rounded border border-border px-2 py-1 text-right font-mono text-sm"
                  />
                </div>
              ))}
            </div>

            <div className="mt-4 flex justify-between text-sm">
              <span className="text-muted-foreground">
                Allocated: <span className="font-mono">{formatINR(splitTotal)}</span>{" "}
                / {formatINR(splitTxn.amount)}
              </span>
              <span
                className={
                  splitTotal > Number(splitTxn.amount)
                    ? "text-red-600"
                    : "text-emerald-700"
                }
              >
                Remainder retained:{" "}
                <span className="font-mono">
                  {formatINR(Number(splitTxn.amount) - splitTotal)}
                </span>
              </span>
            </div>

            {splitMutation.isError && (
              <div className="mt-2 text-xs text-red-600">
                {(splitMutation.error as Error).message}
              </div>
            )}

            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={closeSplitModal}
                className="rounded border border-border px-3 py-1.5 text-sm"
              >
                Cancel
              </button>
              <button
                onClick={() => splitMutation.mutate()}
                disabled={
                  splitMutation.isPending ||
                  splitTotal <= 0 ||
                  splitTotal > Number(splitTxn.amount)
                }
                className="rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
              >
                {splitMutation.isPending ? "Saving…" : "Confirm split"}
              </button>
            </div>
          </div>
        </div>
      )}
    </PageShell>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-xs text-muted-foreground">{label}</label>
      {children}
    </div>
  );
}
