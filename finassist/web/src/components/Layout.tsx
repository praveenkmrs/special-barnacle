import { NavLink, Outlet } from "react-router-dom";
import { cn } from "@/lib/cn";

const ROUTES: { to: string; label: string }[] = [
  { to: "/", label: "Dashboard" },
  { to: "/accounts", label: "Accounts" },
  { to: "/imports", label: "Imports" },
  { to: "/transactions", label: "Transactions" },
  { to: "/review", label: "Review Queue" },
  { to: "/categories", label: "Categories" },
  { to: "/rules", label: "Rules" },
  { to: "/subscriptions", label: "Subscriptions" },
  { to: "/envelopes", label: "Envelopes" },
  { to: "/holdings", label: "Holdings" },
  { to: "/settings", label: "Settings" },
];

export function Layout() {
  return (
    <div className="flex h-full">
      <aside className="w-56 border-r border-border bg-white px-3 py-5">
        <div className="mb-6 px-2 text-lg font-semibold tracking-tight">FinAssist</div>
        <nav className="flex flex-col gap-1">
          {ROUTES.map((r) => (
            <NavLink
              key={r.to}
              to={r.to}
              end={r.to === "/"}
              className={({ isActive }) =>
                cn(
                  "rounded-md px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )
              }
            >
              {r.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="flex-1 overflow-auto p-6">
        <Outlet />
      </main>
    </div>
  );
}
