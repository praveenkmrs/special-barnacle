import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { PageShell } from "@/components/PageShell";
import {
  apiGet,
  apiPost,
  type Account,
  type Category,
  type DupGroup,
  type Transaction,
  type TransferCandidate,
} from "@/lib/api";
import { formatINR } from "@/lib/money";

export function ReviewQueue() {
  const [tab, setTab] = useState<"classification" | "duplicates" | "transfers">(
    "classification",
  );
  return (
    <PageShell
      title="Review Queue"
      description="Classify uncertain transactions, resolve duplicate groups, or confirm transfers."
    >
      <div className="mb-4 flex gap-2 border-b border-border">
        <TabButton active={tab === "classification"} onClick={() => setTab("classification")}>
          Classification
        </TabButton>
        <TabButton active={tab === "duplicates"} onClick={() => setTab("duplicates")}>
          Possible duplicates
        </TabButton>
        <TabButton active={tab === "transfers"} onClick={() => setTab("transfers")}>
          Transfers
        </TabButton>
      </div>
      {tab === "classification" ? (
        <ClassificationTab />
      ) : tab === "duplicates" ? (
        <DuplicatesTab />
      ) : (
        <TransfersTab />
      )}
    </PageShell>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={
        "px-3 py-2 text-sm transition-colors " +
        (active
          ? "border-b-2 border-primary text-foreground"
          : "text-muted-foreground hover:text-foreground")
      }
    >
      {children}
    </button>
  );
}

function ClassificationTab() {
  const qc = useQueryClient();
  const { data: accounts = [] } = useQuery({
    queryKey: ["accounts"],
    queryFn: () => apiGet<Account[]>("/accounts"),
  });
  const { data: categories = [] } = useQuery({
    queryKey: ["categories"],
    queryFn: () => apiGet<Category[]>("/categories"),
  });
  const { data: txns = [], isLoading } = useQuery({
    queryKey: ["review-queue-classify"],
    queryFn: () =>
      apiGet<Transaction[]>("/transactions?needs_review=1&review_reason=classification&limit=200"),
  });

  const classify = useMutation({
    mutationFn: (args: { id: number; category_id: number }) =>
      apiPost(`/transactions/${args.id}/classify`, { category_id: args.category_id }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["review-queue-classify"] });
      qc.invalidateQueries({ queryKey: ["transactions"] });
    },
  });

  const accountName = (id: number) => accounts.find((a) => a.id === id)?.name ?? `#${id}`;
  const childCategories = categories.filter((c) => c.parent_id != null);
  const fuzzyTop3 = (notes: string | null) => {
    if (!notes) return [] as { category_id: number; score: number }[];
    try {
      return (JSON.parse(notes).fuzzy_top3 ?? []) as {
        category_id: number;
        score: number;
      }[];
    } catch {
      return [];
    }
  };

  if (isLoading) return <div>Loading…</div>;
  if (txns.length === 0)
    return <div className="text-sm text-muted-foreground">Inbox zero — nothing to review.</div>;

  return (
    <div className="space-y-3">
      {txns.map((t) => {
        const suggestions = fuzzyTop3(t.notes);
        return (
          <div key={t.id} className="rounded-md border border-border bg-white p-3 text-sm">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="text-xs text-muted-foreground">
                  {t.txn_date} · {accountName(t.account_id)} · {t.type}
                </div>
                <div className="truncate font-medium" title={t.narration}>
                  {t.narration}
                </div>
              </div>
              <div className="font-mono">{formatINR(t.amount)}</div>
            </div>

            {suggestions.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1 text-xs">
                <span className="text-muted-foreground">Suggestions:</span>
                {suggestions.map((s) => {
                  const c = categories.find((x) => x.id === s.category_id);
                  return (
                    <button
                      key={s.category_id}
                      onClick={() => classify.mutate({ id: t.id, category_id: s.category_id })}
                      className="rounded bg-muted px-2 py-0.5 hover:bg-muted/70"
                      title={`score ${s.score.toFixed(3)}`}
                    >
                      {c?.name ?? `#${s.category_id}`}
                    </button>
                  );
                })}
              </div>
            )}

            <div className="mt-2 flex items-center gap-2">
              <select
                onChange={(e) => {
                  const v = Number(e.target.value);
                  if (v) classify.mutate({ id: t.id, category_id: v });
                }}
                className="rounded border border-border px-2 py-1 text-sm"
                defaultValue=""
              >
                <option value="" disabled>
                  Choose category…
                </option>
                {childCategories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function DuplicatesTab() {
  const qc = useQueryClient();
  const { data: groups = [], isLoading } = useQuery({
    queryKey: ["dup-groups"],
    queryFn: () => apiGet<DupGroup[]>("/duplicates/groups"),
  });

  const keepAll = useMutation({
    mutationFn: (gid: number) => apiPost(`/duplicates/${gid}/keep-all`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dup-groups"] });
      qc.invalidateQueries({ queryKey: ["transactions"] });
    },
  });
  const resolve = useMutation({
    mutationFn: (args: { gid: number; keep_ids: number[]; delete_ids: number[] }) =>
      apiPost(`/duplicates/${args.gid}/resolve`, {
        keep_ids: args.keep_ids,
        delete_ids: args.delete_ids,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dup-groups"] });
      qc.invalidateQueries({ queryKey: ["transactions"] });
    },
  });

  if (isLoading) return <div>Loading…</div>;
  if (groups.length === 0)
    return <div className="text-sm text-muted-foreground">No duplicate groups.</div>;

  return (
    <div className="space-y-4">
      {groups.map((g) => (
        <DupGroupCard
          key={g.group_id}
          group={g}
          onKeepAll={() => keepAll.mutate(g.group_id)}
          onResolve={(keep_ids, delete_ids) =>
            resolve.mutate({ gid: g.group_id, keep_ids, delete_ids })
          }
        />
      ))}
    </div>
  );
}

function DupGroupCard({
  group,
  onKeepAll,
  onResolve,
}: {
  group: DupGroup;
  onKeepAll: () => void;
  onResolve: (keep: number[], del: number[]) => void;
}) {
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const toggle = (id: number) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  };

  return (
    <div className="rounded-md border border-purple-300 bg-purple-50/40 p-4">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-sm font-semibold">Group #{group.group_id}</div>
        <div className="flex gap-2">
          <button
            onClick={onKeepAll}
            className="rounded border border-emerald-300 bg-white px-2 py-1 text-xs text-emerald-700"
          >
            Keep all as legitimate
          </button>
          <button
            onClick={() => {
              const del = Array.from(selected);
              const keep = group.rows.map((r) => r.id).filter((id) => !selected.has(id));
              if (del.length === 0) return;
              onResolve(keep, del);
              setSelected(new Set());
            }}
            disabled={selected.size === 0}
            className="rounded border border-red-300 bg-white px-2 py-1 text-xs text-red-700 disabled:opacity-50"
          >
            Mark selected as duplicates ({selected.size})
          </button>
        </div>
      </div>
      <table className="w-full text-sm">
        <thead className="text-left text-muted-foreground">
          <tr>
            <th className="w-8"></th>
            <th>Date</th>
            <th>Narration</th>
            <th className="text-right">Amount</th>
            <th>Reference</th>
            <th>Balance</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {group.rows.map((r) => (
            <tr key={r.id} className="border-t border-purple-200">
              <td>
                <input
                  type="checkbox"
                  checked={selected.has(r.id)}
                  onChange={() => toggle(r.id)}
                />
              </td>
              <td>{r.txn_date}</td>
              <td className="max-w-md truncate" title={r.narration}>
                {r.narration}
              </td>
              <td className="text-right font-mono">{formatINR(r.amount)}</td>
              <td>{r.reference ?? "—"}</td>
              <td className="font-mono">{r.balance_after ? formatINR(r.balance_after) : "—"}</td>
              <td className="text-xs">
                {r.source_file ?? "—"}
                {r.source_page ? `:p${r.source_page}` : ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TransfersTab() {
  const qc = useQueryClient();
  const { data: accounts = [] } = useQuery({
    queryKey: ["accounts"],
    queryFn: () => apiGet<Account[]>("/accounts"),
  });
  const { data: candidates = [], isLoading } = useQuery({
    queryKey: ["transfer-candidates"],
    queryFn: () => apiGet<TransferCandidate[]>("/transfers/candidates"),
  });

  const stage = useMutation({
    mutationFn: () => apiPost<{ staged: number }>("/transfers/stage", {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["transfer-candidates"] });
    },
  });
  const confirm = useMutation({
    mutationFn: (id: number) => apiPost(`/transfers/${id}/confirm`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["transfer-candidates"] });
      qc.invalidateQueries({ queryKey: ["transactions"] });
    },
  });
  const reject = useMutation({
    mutationFn: (id: number) => apiPost(`/transfers/${id}/reject`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["transfer-candidates"] });
      qc.invalidateQueries({ queryKey: ["transactions"] });
    },
  });

  const accountName = (id: number) =>
    accounts.find((a) => a.id === id)?.name ?? `#${id}`;

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          Pairs auto-matched by equal amount within 72 hours across accounts.
        </div>
        <button
          onClick={() => stage.mutate()}
          disabled={stage.isPending}
          className="rounded border border-border bg-white px-3 py-1 text-sm hover:bg-muted disabled:opacity-50"
        >
          {stage.isPending ? "Scanning…" : "Scan for pairs"}
        </button>
      </div>

      {isLoading ? (
        <div>Loading…</div>
      ) : candidates.length === 0 ? (
        <div className="text-sm text-muted-foreground">
          No pending transfer pairs. Click "Scan for pairs" to look for new ones.
        </div>
      ) : (
        <div className="space-y-3">
          {candidates.map((c) => (
            <div
              key={`${c.debit.id}-${c.credit.id}`}
              className="rounded-md border border-blue-300 bg-blue-50/40 p-4"
            >
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div className="rounded border border-border bg-white p-3 text-sm">
                  <div className="mb-1 text-xs font-semibold text-red-700">
                    DEBIT · {accountName(c.debit.account_id)}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {c.debit.txn_date}
                  </div>
                  <div className="truncate font-medium" title={c.debit.narration}>
                    {c.debit.narration}
                  </div>
                  <div className="mt-1 font-mono">{formatINR(c.debit.amount)}</div>
                  {c.debit.reference && (
                    <div className="text-xs text-muted-foreground">
                      Ref: {c.debit.reference}
                    </div>
                  )}
                </div>
                <div className="rounded border border-border bg-white p-3 text-sm">
                  <div className="mb-1 text-xs font-semibold text-emerald-700">
                    CREDIT · {accountName(c.credit.account_id)}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {c.credit.txn_date}
                  </div>
                  <div className="truncate font-medium" title={c.credit.narration}>
                    {c.credit.narration}
                  </div>
                  <div className="mt-1 font-mono">{formatINR(c.credit.amount)}</div>
                  {c.credit.reference && (
                    <div className="text-xs text-muted-foreground">
                      Ref: {c.credit.reference}
                    </div>
                  )}
                </div>
              </div>
              <div className="mt-3 flex justify-end gap-2">
                <button
                  onClick={() => reject.mutate(c.debit.id)}
                  className="rounded border border-red-300 bg-white px-3 py-1 text-xs text-red-700 hover:bg-red-50"
                >
                  Reject
                </button>
                <button
                  onClick={() => confirm.mutate(c.debit.id)}
                  className="rounded border border-emerald-300 bg-white px-3 py-1 text-xs text-emerald-700 hover:bg-emerald-50"
                >
                  Confirm transfer
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
