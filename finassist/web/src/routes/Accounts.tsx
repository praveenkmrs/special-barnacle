import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { PageShell } from "@/components/PageShell";
import { apiGet, apiPost, type Account } from "@/lib/api";
import { formatINR } from "@/lib/money";

export function Accounts() {
  const qc = useQueryClient();
  const { data: accounts = [], isLoading } = useQuery({
    queryKey: ["accounts"],
    queryFn: () => apiGet<Account[]>("/accounts"),
  });

  const [name, setName] = useState("");
  const [type, setType] = useState("bank");
  const [bankCode, setBankCode] = useState("HDFC");
  const [openingBalance, setOpeningBalance] = useState("0");
  const [envelopeOwner, setEnvelopeOwner] = useState("");

  const create = useMutation({
    mutationFn: () =>
      apiPost<Account>("/accounts", {
        name,
        type,
        bank_code: type === "bank" ? bankCode : null,
        envelope_owner: type === "cash_envelope" ? envelopeOwner : null,
        opening_balance: openingBalance,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["accounts"] });
      setName("");
    },
  });

  return (
    <PageShell title="Accounts" description="Banks, credit cards, cash envelopes, and brokers.">
      <form
        className="mb-6 flex flex-wrap items-end gap-3"
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
            placeholder="HDFC Salary"
          />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground">Type</label>
          <select
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="rounded border border-border px-2 py-1 text-sm"
          >
            <option value="bank">bank</option>
            <option value="credit_card">credit_card</option>
            <option value="cash_envelope">cash_envelope</option>
            <option value="broker">broker</option>
            <option value="mf">mf</option>
            <option value="epf">epf</option>
            <option value="nps">nps</option>
          </select>
        </div>
        {type === "bank" && (
          <div>
            <label className="block text-xs text-muted-foreground">Bank</label>
            <select
              value={bankCode}
              onChange={(e) => setBankCode(e.target.value)}
              className="rounded border border-border px-2 py-1 text-sm"
            >
              <option value="HDFC">HDFC</option>
            </select>
          </div>
        )}
        {type === "cash_envelope" && (
          <div>
            <label className="block text-xs text-muted-foreground">Owner</label>
            <input
              value={envelopeOwner}
              onChange={(e) => setEnvelopeOwner(e.target.value)}
              className="rounded border border-border px-2 py-1 text-sm"
              placeholder="Mom"
            />
          </div>
        )}
        <div>
          <label className="block text-xs text-muted-foreground">Opening balance</label>
          <input
            value={openingBalance}
            onChange={(e) => setOpeningBalance(e.target.value)}
            className="w-32 rounded border border-border px-2 py-1 text-sm"
          />
        </div>
        <button
          type="submit"
          className="rounded bg-primary px-3 py-1.5 text-sm text-primary-foreground"
          disabled={create.isPending}
        >
          {create.isPending ? "…" : "Add account"}
        </button>
        {create.error && (
          <span className="text-xs text-red-600">{(create.error as Error).message}</span>
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
              <th>Bank</th>
              <th>Owner</th>
              <th className="text-right">Opening Balance</th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((a) => (
              <tr key={a.id} className="border-t border-border">
                <td className="py-2">{a.name}</td>
                <td>{a.type}</td>
                <td>{a.bank_code ?? "—"}</td>
                <td>{a.envelope_owner ?? "—"}</td>
                <td className="text-right font-mono">{formatINR(a.opening_balance)}</td>
              </tr>
            ))}
            {accounts.length === 0 && (
              <tr>
                <td colSpan={5} className="py-4 text-center text-muted-foreground">
                  No accounts yet — add one above.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </PageShell>
  );
}
