import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { PageShell } from "@/components/PageShell";
import {
  apiGet,
  apiPostForm,
  type Account,
  type ImportRecord,
  type ImportResult,
} from "@/lib/api";

export function Imports() {
  const qc = useQueryClient();
  const { data: accounts = [] } = useQuery({
    queryKey: ["accounts"],
    queryFn: () => apiGet<Account[]>("/accounts"),
  });
  const { data: imports = [], isLoading } = useQuery({
    queryKey: ["imports"],
    queryFn: () => apiGet<ImportRecord[]>("/imports"),
  });

  const [accountId, setAccountId] = useState<number | "">("");
  const [password, setPassword] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [lastResult, setLastResult] = useState<ImportResult | null>(null);

  const upload = useMutation({
    mutationFn: async () => {
      if (!file || accountId === "") throw new Error("file + account required");
      const fd = new FormData();
      fd.append("file", file);
      fd.append("account_id", String(accountId));
      if (password) fd.append("password", password);
      return apiPostForm<ImportResult>("/imports", fd);
    },
    onSuccess: (result) => {
      setLastResult(result);
      qc.invalidateQueries({ queryKey: ["imports"] });
      qc.invalidateQueries({ queryKey: ["transactions"] });
    },
  });

  return (
    <PageShell
      title="Imports"
      description="Upload an HDFC PDF or CSV statement. Encrypted PDFs ask for the 9-digit Customer ID."
    >
      <form
        className="mb-6 space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          upload.mutate();
        }}
      >
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-xs text-muted-foreground">Account</label>
            <select
              value={accountId}
              onChange={(e) =>
                setAccountId(e.target.value === "" ? "" : Number(e.target.value))
              }
              className="rounded border border-border px-2 py-1 text-sm"
            >
              <option value="">Select…</option>
              {accounts
                .filter((a) => a.type === "bank" || a.type === "credit_card")
                .map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-muted-foreground">PDF password (optional)</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="9-digit Customer ID for HDFC"
              className="w-64 rounded border border-border px-2 py-1 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground">Statement file</label>
            <input
              type="file"
              accept=".pdf,.csv,.tsv,.txt"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="text-sm"
            />
          </div>
          <button
            type="submit"
            className="rounded bg-primary px-3 py-1.5 text-sm text-primary-foreground"
            disabled={upload.isPending || !file || accountId === ""}
          >
            {upload.isPending ? "Uploading…" : "Upload"}
          </button>
        </div>
        {upload.error && (
          <div className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
            {(upload.error as Error).message}
          </div>
        )}
        {lastResult && (
          <div className="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm">
            <div className="font-medium">{lastResult.status}</div>
            <div>
              imported {lastResult.rows_imported} · duplicates skipped{" "}
              {lastResult.rows_duplicate} · ambiguous (review) {lastResult.rows_ambiguous} ·
              failed {lastResult.rows_failed}
            </div>
            {lastResult.period_start && lastResult.period_end && (
              <div className="text-xs text-muted-foreground">
                period {lastResult.period_start} → {lastResult.period_end}
              </div>
            )}
            {lastResult.error_log && (
              <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs text-red-700">
                {lastResult.error_log}
              </pre>
            )}
          </div>
        )}
      </form>

      <h2 className="mb-2 text-sm font-semibold">History</h2>
      {isLoading ? (
        <div>Loading…</div>
      ) : imports.length === 0 ? (
        <div className="text-sm text-muted-foreground">No imports yet.</div>
      ) : (
        <table className="w-full text-sm">
          <thead className="text-left text-muted-foreground">
            <tr>
              <th className="py-2">File</th>
              <th>Bank</th>
              <th>Period</th>
              <th>Imported</th>
              <th>Dupes</th>
              <th>Failed</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {imports.map((i) => (
              <tr key={i.id} className="border-t border-border">
                <td className="py-2">{i.source_file ?? "—"}</td>
                <td>{i.bank_code ?? "—"}</td>
                <td>
                  {i.period_start ?? "—"} → {i.period_end ?? "—"}
                </td>
                <td>{i.rows_imported}</td>
                <td>{i.rows_duplicate}</td>
                <td>{i.rows_failed}</td>
                <td>{i.status ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </PageShell>
  );
}
