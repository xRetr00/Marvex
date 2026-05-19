import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, Brain, Cable, Clock3, Database, Gauge, GitBranch, History, KeyRound, ListChecks, MonitorCog, Search, Server, Settings, ShieldAlert, ShieldCheck, Store, Wrench } from "lucide-react";
import { fetchSnapshot } from "./lib/api";
import { Dashboard } from "./views/Dashboard";
import { Approvals } from "./views/Approvals";
import { SafeTable } from "./views/TableViews";
import { ApprovalHistoryView, AutoFetchView, ConnectorListView, DiagnosticsView, McpMarketplaceView, MemoryInspectView, MemorySourcesView, MemoryTreesView, PolicyView, SkillsMarketplaceView, TraceSearchView } from "./views/ExpandedViews";
import { TabButton } from "./components/ui/tabs";
import { Card, CardContent } from "./components/ui/card";

const views = [
  { id: "dashboard", label: "Dashboard", icon: Gauge },
  { id: "approvals", label: "Approvals", icon: ShieldCheck },
  { id: "runtime_execution", label: "Runtime Execution", icon: MonitorCog },
  { id: "approval_history", label: "Approval History", icon: History },
  { id: "traces", label: "Traces", icon: Activity },
  { id: "trace_search", label: "Trace Search", icon: Search },
  { id: "telemetry", label: "Telemetry", icon: MonitorCog },
  { id: "providers", label: "Providers", icon: Server },
  { id: "capabilities", label: "Capabilities / Tools", icon: Wrench },
  { id: "tool_policy", label: "Tool Risk Policy", icon: ShieldAlert },
  { id: "mcp", label: "MCP", icon: ListChecks },
  { id: "mcp_marketplace", label: "MCP Marketplace", icon: Store },
  { id: "skills", label: "Skills", icon: Brain },
  { id: "skills_marketplace", label: "Skills Marketplace", icon: Store },
  { id: "memory", label: "Memory / Sessions", icon: Database },
  { id: "memory_inspect", label: "Memory Inspect", icon: Database },
  { id: "connectors", label: "Connectors", icon: Cable },
  { id: "memory_sources", label: "Memory Sources", icon: Database },
  { id: "autofetch", label: "Auto-Fetch", icon: Clock3 },
  { id: "memory_trees", label: "Memory Trees", icon: GitBranch },
  { id: "diagnostics", label: "Runtime Diagnostics", icon: MonitorCog },
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
            <p className="text-xs text-muted-foreground">Local admin dashboard for approvals, marketplaces, telemetry, capabilities, policies, and safe runtime views.</p>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground"><KeyRound size={16} /> local token required</div>
        </div>
      </header>
      <div className="grid lg:grid-cols-[260px_1fr]">
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
  if (active === "runtime_execution") return <RuntimeExecutionView snapshot={snapshot} />;
  if (active === "approval_history") return <ApprovalHistoryView />;
  if (active === "traces") return <SafeTable title="Traces" rows={snapshot.traces} empty="No safe trace projections available." />;
  if (active === "trace_search") return <TraceSearchView />;
  if (active === "telemetry") return <SafeTable title="Telemetry" rows={[snapshot.telemetry]} empty="No telemetry summary available." />;
  if (active === "providers") return <SafeTable title="Providers" rows={snapshot.providers} empty="No providers registered." />;
  if (active === "capabilities") return <div className="space-y-4"><SafeTable title="Capability Registry" rows={snapshot.capabilities} empty="No capabilities eligible." /><SafeTable title="Tools" rows={snapshot.tools} empty="No tools available." /></div>;
  if (active === "tool_policy") return <PolicyView />;
  if (active === "mcp") return <SafeTable title="MCP Servers / Tools" rows={snapshot.mcp_servers} empty="No allowlisted MCP servers." />;
  if (active === "mcp_marketplace") return <McpMarketplaceView />;
  if (active === "skills") return <SafeTable title="Skills" rows={snapshot.skills} empty="No validated skills." />;
  if (active === "skills_marketplace") return <SkillsMarketplaceView />;
  if (active === "memory") return <div className="space-y-4"><SafeTable title="Memory Safe Summaries" rows={snapshot.memory} empty="No memory summaries." /><SafeTable title="Sessions / Conversations" rows={snapshot.sessions} empty="No session refs." /></div>;
  if (active === "memory_inspect") return <MemoryInspectView />;
  if (active === "connectors") return <ConnectorListView />;
  if (active === "memory_sources") return <MemorySourcesView />;
  if (active === "autofetch") return <AutoFetchView />;
  if (active === "memory_trees") return <MemoryTreesView />;
  if (active === "diagnostics") return <DiagnosticsView />;
  return <SafeTable title="Settings" rows={[snapshot.settings]} empty="No settings exposed." />;
}

function LoadingState() {
  return <Card><CardContent className="p-6 text-sm text-muted-foreground">Loading local control plane data...</CardContent></Card>;
}

function ErrorState({ message }: { message: string }) {
  return <Card><CardContent className="p-6"><div className="font-medium">Control Plane unavailable</div><p className="mt-1 text-sm text-muted-foreground">{message}</p></CardContent></Card>;
}


function RuntimeExecutionView({ snapshot }: { snapshot: import("./lib/schemas").ControlSnapshot }) {
  const loop = snapshot.agent_loops[0] ?? {};
  const approvalState = Number(loop.pending_approval_count ?? 0) > 0 ? "pending" : "none";
  const resultStatus = String(loop.result_status ?? "not_started");
  const continuationStatus = loop.provider_continuation_ready ? "ready" : "not_ready";
  const finalStatus = loop.final_response_ready ? "ready" : "not_ready";
  const riskLevel = String(loop.risk_level ?? "safe");
  const traceRef = String(loop.safe_trace_ref ?? loop.trace_id ?? "none");
  const proposalStatus = approvalState === "pending" ? "pending_approval" : resultStatus;
  const proposalRows = [{ proposal_id: String(loop.provider_tool_proposal_id ?? "none"), status: proposalStatus, risk_level: riskLevel, trace_ref: traceRef, raw_provider_payload_persisted: false }];
  const browserRows = [{ action_kind: String(loop.browser_action_kind ?? "none"), approval_state: approvalState, status: resultStatus, raw_dom_persisted: false, raw_screenshot_persisted: false }];
  const mcpRows = [{ status: Number(loop.mcp_tool_count ?? 0) > 0 ? "succeeded" : "not_started", tool_count: Number(loop.mcp_tool_count ?? 0), raw_mcp_payload_persisted: false }];
  const continuationRows = [{ status: continuationStatus, backend: String(loop.provider_continuation_backend ?? "not_selected"), input_ready: Boolean(loop.provider_continuation_input_ready), raw_provider_payload_persisted: false }];
  const finalRows = [{ status: finalStatus, raw_transcript_persisted: false }];
  const approvalRows = snapshot.approvals?.approvals.map((approval) => ({ approval_request_id: approval.approval_request_id, state: approval.status, risk_level: approval.risk_level, execution_started: false })) ?? [];
  return <div className="space-y-4"><SafeTable title="Tool Calls / Provider Proposals" rows={proposalRows} empty="No provider proposals." /><SafeTable title="Approval Resume / Deny / Cancel" rows={approvalRows} empty="No pending approval state." /><SafeTable title="Browser Actions" rows={browserRows} empty="No browser actions." /><SafeTable title="MCP Calls" rows={mcpRows} empty="No MCP calls." /><SafeTable title="Provider Continuation" rows={continuationRows} empty="No provider continuation state." /><SafeTable title="Final Response" rows={finalRows} empty="No final response state." /><SafeTable title="Trace Links" rows={traceRef === "none" ? [] : [{ trace_ref: traceRef }]} empty="No trace refs." /></div>;
}
