import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { PageShell } from "@/components/PageShell";
import { apiGet, apiPost, type Category, type Rule } from "@/lib/api";

export function Rules() {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>("");

  const { data: categories = [] } = useQuery({
    queryKey: ["categories"],
    queryFn: () => apiGet<Category[]>("/categories"),
  });
  const { data: rules = [], isLoading } = useQuery({
    queryKey: ["rules", statusFilter],
    queryFn: () =>
      apiGet<Rule[]>(`/rules${statusFilter ? `?status=${statusFilter}` : ""}`),
  });

  const promoteAll = useMutation({
    mutationFn: () => apiPost<{ promoted: number }>("/rules/promote-eligible", {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rules"] }),
  });
  const promote = useMutation({
    mutationFn: (id: number) => apiPost(`/rules/${id}/promote`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rules"] }),
  });
  const disable = useMutation({
    mutationFn: (id: number) => apiPost(`/rules/${id}/disable`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rules"] }),
  });

  const [pattern, setPattern] = useState("");
  const [categoryId, setCategoryId] = useState<number | "">("");
  const create = useMutation({
    mutationFn: () =>
      apiPost<Rule>("/rules", {
        pattern,
        pattern_type: "narration",
        category_id: categoryId === "" ? null : categoryId,
        status: "active",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["rules"] });
      setPattern("");
    },
  });

  const catName = (id: number | null) =>
    id == null ? "—" : categories.find((c) => c.id === id)?.name ?? `#${id}`;

  return (
    <PageShell title="Rules" description="Tier 1/2 classification rules.">
      <form
        className="mb-4 flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (!pattern || categoryId === "") return;
          create.mutate();
        }}
      >
        <div>
          <label className="block text-xs text-muted-foreground">Pattern (regex)</label>
          <input
            value={pattern}
            onChange={(e) => setPattern(e.target.value)}
            className="w-72 rounded border border-border px-2 py-1 text-sm font-mono"
            placeholder=".*NETFLIX.*"
          />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground">Category</label>
          <select
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value === "" ? "" : Number(e.target.value))}
            className="rounded border border-border px-2 py-1 text-sm"
          >
            <option value="">Choose…</option>
            {categories
              .filter((c) => c.parent_id != null)
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
          </select>
        </div>
        <button
          type="submit"
          className="rounded bg-primary px-3 py-1.5 text-sm text-primary-foreground"
          disabled={create.isPending}
        >
          Add active rule
        </button>
      </form>

      <div className="mb-3 flex items-center gap-3">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded border border-border px-2 py-1 text-sm"
        >
          <option value="">All statuses</option>
          <option value="active">active</option>
          <option value="candidate">candidate</option>
          <option value="disabled">disabled</option>
          <option value="blacklisted">blacklisted</option>
        </select>
        <button
          onClick={() => promoteAll.mutate()}
          className="rounded border border-border bg-white px-2 py-1 text-sm"
        >
          Promote eligible candidates
        </button>
      </div>

      {isLoading ? (
        <div>Loading…</div>
      ) : rules.length === 0 ? (
        <div className="text-sm text-muted-foreground">No rules.</div>
      ) : (
        <table className="w-full text-sm">
          <thead className="text-left text-muted-foreground">
            <tr>
              <th className="py-2">Pattern</th>
              <th>Category</th>
              <th>Status</th>
              <th>Hits</th>
              <th>Conflicts</th>
              <th>Last hit</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((r) => (
              <tr key={r.id} className="border-t border-border">
                <td className="py-2 font-mono text-xs">{r.pattern}</td>
                <td>{catName(r.category_id)}</td>
                <td>
                  <StatusBadge status={r.status} />
                </td>
                <td>{r.hit_count}</td>
                <td>{r.conflict_count}</td>
                <td className="text-xs">{r.last_hit_at?.slice(0, 10) ?? "—"}</td>
                <td className="space-x-1 text-xs">
                  {r.status === "candidate" && (
                    <button
                      onClick={() => promote.mutate(r.id)}
                      className="rounded bg-emerald-100 px-2 py-0.5 text-emerald-800"
                    >
                      promote
                    </button>
                  )}
                  {r.status !== "disabled" && (
                    <button
                      onClick={() => disable.mutate(r.id)}
                      className="rounded bg-red-100 px-2 py-0.5 text-red-800"
                    >
                      disable
                    </button>
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

function StatusBadge({ status }: { status: string }) {
  const cls: Record<string, string> = {
    active: "bg-emerald-100 text-emerald-800",
    candidate: "bg-amber-100 text-amber-800",
    disabled: "bg-red-100 text-red-800",
    blacklisted: "bg-gray-200 text-gray-700",
  };
  return (
    <span className={`rounded px-2 py-0.5 text-xs ${cls[status] ?? "bg-muted"}`}>{status}</span>
  );
}
