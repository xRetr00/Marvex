import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, Brain, Database, Gauge, KeyRound, ListChecks, MonitorCog, Server, Settings, ShieldCheck, Wrench } from "lucide-react";
import { fetchSnapshot } from "./lib/api";
import { Dashboard } from "./views/Dashboard";
import { Approvals } from "./views/Approvals";
import { SafeTable } from "./views/TableViews";
import { TabButton } from "./components/ui/tabs";
import { Card, CardContent } from "./components/ui/card";

const views = [
  { id: "dashboard", label: "Dashboard", icon: Gauge },
  { id: "approvals", label: "Approvals", icon: ShieldCheck },
  { id: "traces", label: "Traces", icon: Activity },
  { id: "telemetry", label: "Telemetry", icon: MonitorCog },
  { id: "providers", label: "Providers", icon: Server },
  { id: "capabilities", label: "Capabilities / Tools", icon: Wrench },
  { id: "mcp", label: "MCP", icon: ListChecks },
  { id: "skills", label: "Skills", icon: Brain },
  { id: "memory", label: "Memory / Sessions", icon: Database },
  { id: "settings", label: "Settings", icon: Settings }
] as const;

type ViewId = typeof views[number]["id"];

export function App() {
  const [active, setActive] = useState<ViewId>("dashboard");
  const snapshotQuery = useQuery({ queryKey: ["control-snapshot"], queryFn: fetchSnapshot, retry: false });
  const title = useMemo(() => views.find((view) => view.id === active)?.label ?? "Dashboard", [active]);

  return (
    <div className="min-h-screen">
      <header className="border-b border-border bg-card">
        <div className="flex min-h-14 items-center justify-between px-4">
          <div>
            <h1 className="text-base font-semibold">Marvex Control Plane</h1>
            <p className="text-xs text-muted-foreground">Local admin dashboard for approvals, telemetry, capabilities, and safe runtime views.</p>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground"><KeyRound size={16} /> local token required</div>
        </div>
      </header>
      <div className="grid lg:grid-cols-[250px_1fr]">
        <aside className="border-b border-border bg-card p-3 lg:min-h-[calc(100vh-57px)] lg:border-b-0 lg:border-r">
          <nav className="grid gap-1">
            {views.map(({ id, label, icon: Icon }) => (
              <TabButton key={id} active={active === id} onClick={() => setActive(id)}><Icon className="mr-2" size={16} />{label}</TabButton>
            ))}
          </nav>
        </aside>
        <main className="p-4 lg:p-6">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="text-xl font-semibold">{title}</h2>
            <span className="text-xs text-muted-foreground">Safe projections only</span>
          </div>
          {snapshotQuery.isLoading && <LoadingState />}
          {snapshotQuery.isError && <ErrorState message={snapshotQuery.error.message} />}
          {snapshotQuery.data && <View active={active} snapshot={snapshotQuery.data} />}
        </main>
      </div>
    </div>
  );
}

function View({ active, snapshot }: { active: ViewId; snapshot: import("./lib/schemas").ControlSnapshot }) {
  if (active === "dashboard") return <Dashboard snapshot={snapshot} />;
  if (active === "approvals") return <Approvals approvals={snapshot.approvals?.approvals ?? []} />;
  if (active === "traces") return <SafeTable title="Traces" rows={snapshot.traces} empty="No safe trace projections available." />;
  if (active === "telemetry") return <SafeTable title="Telemetry" rows={[snapshot.telemetry]} empty="No telemetry summary available." />;
  if (active === "providers") return <SafeTable title="Providers" rows={snapshot.providers} empty="No providers registered." />;
  if (active === "capabilities") return <div className="space-y-4"><SafeTable title="Capabilities" rows={snapshot.capabilities} empty="No capabilities eligible." /><SafeTable title="Tools" rows={snapshot.tools} empty="No tools available." /></div>;
  if (active === "mcp") return <SafeTable title="MCP Servers / Tools" rows={snapshot.mcp_servers} empty="No allowlisted MCP servers." />;
  if (active === "skills") return <SafeTable title="Skills" rows={snapshot.skills} empty="No validated skills." />;
  if (active === "memory") return <div className="space-y-4"><SafeTable title="Memory Safe Summaries" rows={snapshot.memory} empty="No memory summaries." /><SafeTable title="Sessions / Conversations" rows={snapshot.sessions} empty="No session refs." /></div>;
  return <SafeTable title="Settings" rows={[snapshot.settings]} empty="No settings exposed." />;
}

function LoadingState() {
  return <Card><CardContent className="p-6 text-sm text-muted-foreground">Loading local control plane data...</CardContent></Card>;
}

function ErrorState({ message }: { message: string }) {
  return <Card><CardContent className="p-6"><div className="font-medium">Control Plane unavailable</div><p className="mt-1 text-sm text-muted-foreground">{message}</p></CardContent></Card>;
}