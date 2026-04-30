import { PageShell } from "@/components/PageShell";

const ENTITIES = [
  "transactions",
  "accounts",
  "categories",
  "rules",
  "subscriptions",
  "holdings",
  "holding_transactions",
  "imports",
  "nav_cache",
];

export function Settings() {
  return (
    <PageShell
      title="Settings"
      description="Backups & exports. Application settings live in the API config."
    >
      <section className="space-y-3">
        <h3 className="text-sm font-semibold">Export to CSV</h3>
        <p className="text-sm text-muted-foreground">
          Download every entity in the database as CSV. Use these for backups or analysis in
          Excel/pandas.
        </p>
        <div className="grid grid-cols-3 gap-2">
          {ENTITIES.map((e) => (
            <a
              key={e}
              href={`/api/exports/${e}.csv`}
              className="rounded border border-border bg-white px-3 py-2 text-sm hover:bg-muted"
            >
              {e}.csv
            </a>
          ))}
        </div>
      </section>

      <section className="mt-8 space-y-2">
        <h3 className="text-sm font-semibold">About</h3>
        <p className="text-sm text-muted-foreground">
          FinAssist v0.1 · local-first · HDFC Bank vertical slice. SQLite database is at{" "}
          <code className="rounded bg-muted px-1 py-0.5">/data/finassist.db</code> in Docker, or{" "}
          <code className="rounded bg-muted px-1 py-0.5">~/.finassist/finassist.db</code> in dev.
        </p>
      </section>
    </PageShell>
  );
}
