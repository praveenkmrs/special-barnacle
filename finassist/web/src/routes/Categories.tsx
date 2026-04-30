import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { PageShell } from "@/components/PageShell";
import { apiGet, apiPost, type Category } from "@/lib/api";

export function Categories() {
  const qc = useQueryClient();
  const { data: categories = [], isLoading } = useQuery({
    queryKey: ["categories"],
    queryFn: () => apiGet<Category[]>("/categories"),
  });

  const [name, setName] = useState("");
  const [parentId, setParentId] = useState<number | "">("");

  const create = useMutation({
    mutationFn: () =>
      apiPost<Category>("/categories", {
        name,
        parent_id: parentId === "" ? null : parentId,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["categories"] });
      setName("");
    },
  });

  const top = categories.filter((c) => c.parent_id == null);
  const children = (pid: number) => categories.filter((c) => c.parent_id === pid);

  return (
    <PageShell title="Categories" description="Default taxonomy + your additions.">
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
          />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground">Parent</label>
          <select
            value={parentId}
            onChange={(e) => setParentId(e.target.value === "" ? "" : Number(e.target.value))}
            className="rounded border border-border px-2 py-1 text-sm"
          >
            <option value="">— top level —</option>
            {top.map((c) => (
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
          Add
        </button>
      </form>

      {isLoading ? (
        <div>Loading…</div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {top.map((parent) => (
            <div key={parent.id} className="rounded border border-border bg-muted/20 p-3">
              <div className="mb-1 flex items-center gap-2 text-sm font-semibold">
                {parent.name}
                {parent.is_transfer === 1 && (
                  <span className="rounded bg-blue-100 px-1.5 py-0.5 text-xs text-blue-800">
                    transfer
                  </span>
                )}
                {parent.is_income === 1 && (
                  <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-xs text-emerald-800">
                    income
                  </span>
                )}
              </div>
              <ul className="space-y-0.5 text-sm">
                {children(parent.id).map((c) => (
                  <li key={c.id} className="text-muted-foreground">
                    · {c.name}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </PageShell>
  );
}
