import type { ReactNode } from "react";

interface Props {
  title: string;
  description?: string;
  children?: ReactNode;
}

export function PageShell({ title, description, children }: Props) {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && (
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        )}
      </header>
      <div className="rounded-lg border border-border bg-white p-6 shadow-sm">
        {children ?? (
          <div className="text-sm text-muted-foreground">
            Phase 1 shell — feature lands in a later phase.
          </div>
        )}
      </div>
    </div>
  );
}
