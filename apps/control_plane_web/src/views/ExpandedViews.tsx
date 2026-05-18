import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Search, ShieldAlert, Trash2 } from "lucide-react";
import {
  enableSkill,
  fetchApprovalHistory,
  fetchAutoFetch,
  fetchMemoryDailyDigest,
  fetchMemoryDrillDown,
  fetchConnectors,
  fetchDiagnostics,
  fetchMcpMarketplace,
  fetchMemoryInspect,
  fetchMemorySourceTree,
  fetchMemoryTopicTree,
  fetchMemoryTreeScoring,
  fetchMemoryTreeSearch,
  fetchPolicies,
  fetchSources,
  forgetSource,
  fetchSkillsMarketplace,
  fetchTraceSearch,
  forgetMemory,
  proposeMcpAllowlist,
  setAutoFetchState
} from "../lib/api";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { SafeTable } from "./TableViews";

function InlineState({ message }: { message: string }) {
  return <Card><CardContent className="p-4 text-sm text-muted-foreground">{message}</CardContent></Card>;
}

export function McpMarketplaceView() {
  const query = useQuery({ queryKey: ["mcp-marketplace"], queryFn: fetchMcpMarketplace, retry: false });
  const mutation = useMutation({ mutationFn: proposeMcpAllowlist });
  if (query.isLoading) return <InlineState message="Loading MCP registry metadata..." />;
  if (query.isError) return <InlineState message={query.error.message} />;
  const entries = query.data?.entries ?? [];
  return (
    <div className="space-y-4">
      <Card><CardHeader><CardTitle>MCP Marketplace</CardTitle></CardHeader><CardContent className="space-y-3"><p className="text-sm text-muted-foreground">Official registry metadata is browsed read-only. Allowlisting creates a proposal only.</p>{entries.map((entry) => <Button key={String(entry.server_id)} variant="outline" onClick={() => mutation.mutate(String(entry.server_id))}><ShieldAlert className="mr-2" size={16} />Propose allowlist: {String(entry.server_id)}</Button>)}{mutation.data && <p className="text-sm">Proposal created: {String(mutation.data.proposal_id)}</p>}</CardContent></Card>
      <SafeTable title="Registry Servers" rows={entries} empty="No MCP registry metadata available." />
    </div>
  );
}

export function SkillsMarketplaceView() {
  const query = useQuery({ queryKey: ["skills-marketplace"], queryFn: fetchSkillsMarketplace, retry: false });
  const mutation = useMutation({ mutationFn: enableSkill });
  if (query.isLoading) return <InlineState message="Loading local skill metadata..." />;
  if (query.isError) return <InlineState message={query.error.message} />;
  const entries = query.data?.entries ?? [];
  return (
    <div className="space-y-4">
      <Card><CardHeader><CardTitle>Skills Marketplace</CardTitle></CardHeader><CardContent className="space-y-3"><p className="text-sm text-muted-foreground">Skills are local approved metadata only. Script execution and remote loading stay disabled.</p>{entries.map((entry) => <Button key={String(entry.skill_id)} variant="outline" onClick={() => mutation.mutate(String(entry.skill_id))}><CheckCircle2 className="mr-2" size={16} />Enable metadata: {String(entry.skill_id)}</Button>)}{mutation.data && <p className="text-sm">Enablement state: {String(mutation.data.reason_code)}</p>}</CardContent></Card>
      <SafeTable title="Skill Packages" rows={entries} empty="No local skill packages available." />
      <SafeTable title="Prompt Contribution Preview" rows={query.data?.previews ?? []} empty="No prompt contributions available." />
    </div>
  );
}

export function MemoryInspectView() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["memory-inspect"], queryFn: fetchMemoryInspect, retry: false });
  const mutation = useMutation({ mutationFn: forgetMemory, onSuccess: () => queryClient.invalidateQueries({ queryKey: ["memory-inspect"] }) });
  if (query.isLoading) return <InlineState message="Loading safe memory previews..." />;
  if (query.isError) return <InlineState message={query.error.message} />;
  const rows = query.data?.records ?? [];
  return (
    <div className="space-y-4">
      <Card><CardHeader><CardTitle>Memory Inspect / Forget</CardTitle></CardHeader><CardContent className="space-y-3"><p className="text-sm text-muted-foreground">Memory inspection uses previews only; forget requests route through backend policy state.</p>{rows.map((row) => <Button key={String(row.memory_ref)} variant="outline" onClick={() => mutation.mutate(String(row.memory_ref))}><Trash2 className="mr-2" size={16} />Forget {String(row.memory_ref)}</Button>)}</CardContent></Card>
      <SafeTable title="Memory Safe Previews" rows={rows} empty="No memory records available." />
    </div>
  );
}

export function TraceSearchView() {
  const query = useQuery({ queryKey: ["trace-search"], queryFn: () => fetchTraceSearch(), retry: false });
  if (query.isLoading) return <InlineState message="Searching safe trace summaries..." />;
  if (query.isError) return <InlineState message={query.error.message} />;
  return <div className="space-y-4"><Card><CardHeader><CardTitle>Trace Search</CardTitle></CardHeader><CardContent className="flex items-center gap-2 text-sm text-muted-foreground"><Search size={16} /> Filter-ready safe trace summaries only.</CardContent></Card><SafeTable title="Trace Results" rows={query.data?.traces ?? []} empty="No trace results." /></div>;
}

export function ApprovalHistoryView() {
  const query = useQuery({ queryKey: ["approval-history"], queryFn: fetchApprovalHistory, retry: false });
  if (query.isLoading) return <InlineState message="Loading approval history..." />;
  if (query.isError) return <InlineState message={query.error.message} />;
  return <SafeTable title="Approval History" rows={query.data?.decisions ?? []} empty="No approval history available." />;
}

export function PolicyView() {
  const query = useQuery({ queryKey: ["policies"], queryFn: fetchPolicies, retry: false });
  if (query.isLoading) return <InlineState message="Loading policy summaries..." />;
  if (query.isError) return <InlineState message={query.error.message} />;
  return <SafeTable title="Tool Risk Policy" rows={query.data?.policies ?? []} empty="No policy summaries available." />;
}

export function DiagnosticsView() {
  const query = useQuery({ queryKey: ["diagnostics"], queryFn: fetchDiagnostics, retry: false });
  if (query.isLoading) return <InlineState message="Loading runtime diagnostics..." />;
  if (query.isError) return <InlineState message={query.error.message} />;
  return <SafeTable title="Runtime Diagnostics" rows={query.data ? [query.data] : []} empty="No diagnostics available." />;
}

export function ConnectorListView() {
  const query = useQuery({ queryKey: ["connectors"], queryFn: fetchConnectors, retry: false });
  if (query.isLoading) return <InlineState message="Loading connector manifests..." />;
  if (query.isError) return <InlineState message={query.error.message} />;
  return <SafeTable title="Connectors" rows={query.data?.connectors ?? []} empty="No connector manifests available." />;
}

export function MemorySourcesView() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["memory-sources"], queryFn: fetchSources, retry: false });
  const mutation = useMutation({ mutationFn: forgetSource, onSuccess: () => queryClient.invalidateQueries({ queryKey: ["memory-sources"] }) });
  if (query.isLoading) return <InlineState message="Loading memory sources..." />;
  if (query.isError) return <InlineState message={query.error.message} />;
  const rows = query.data?.sources ?? [];
  return <div className="space-y-4"><Card><CardHeader><CardTitle>Source Controls</CardTitle></CardHeader><CardContent className="space-y-3">{rows.map((row) => <Button key={String(row.source_id)} variant="outline" onClick={() => mutation.mutate(String(row.source_id))}><Trash2 className="mr-2" size={16} />Forget source {String(row.source_id)}</Button>)}{mutation.data && <p className="text-sm">Forget requested: {mutation.data.source_id}</p>}</CardContent></Card><SafeTable title="Memory Sources" rows={rows} empty="No memory sources available." /></div>;
}

export function AutoFetchView() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["autofetch"], queryFn: fetchAutoFetch, retry: false });
  const mutation = useMutation({ mutationFn: ({ connectorId, action }: { connectorId: string; action: "enable" | "disable" | "pause" }) => setAutoFetchState(connectorId, action), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["autofetch"] }) });
  if (query.isLoading) return <InlineState message="Loading auto-fetch policies..." />;
  if (query.isError) return <InlineState message={query.error.message} />;
  const rows = query.data?.policies ?? [];
  return <div className="space-y-4"><Card><CardHeader><CardTitle>Auto-Fetch Controls</CardTitle></CardHeader><CardContent className="flex flex-wrap gap-2">{rows.map((row) => <div key={String(row.connector_id)} className="flex gap-2"><Button variant="outline" onClick={() => mutation.mutate({ connectorId: String(row.connector_id), action: "enable" })}>Enable {String(row.connector_id)}</Button><Button variant="outline" onClick={() => mutation.mutate({ connectorId: String(row.connector_id), action: "pause" })}>Pause</Button><Button variant="outline" onClick={() => mutation.mutate({ connectorId: String(row.connector_id), action: "disable" })}>Disable</Button></div>)}</CardContent></Card><SafeTable title="Auto-Fetch" rows={rows} empty="No auto-fetch policies available." /></div>;
}

export function MemoryTreesView() {
  const search = useQuery({ queryKey: ["memory-tree-search"], queryFn: () => fetchMemoryTreeSearch("evidence"), retry: false });
  const sourceTree = useQuery({ queryKey: ["memory-source-tree"], queryFn: () => fetchMemorySourceTree("source-github"), retry: false });
  const topicTree = useQuery({ queryKey: ["memory-topic-tree"], queryFn: () => fetchMemoryTopicTree("memory-tree"), retry: false });
  const daily = useQuery({ queryKey: ["memory-daily-digest"], queryFn: () => fetchMemoryDailyDigest("2026-05-18"), retry: false });
  const drillDown = useQuery({ queryKey: ["memory-drill-down"], queryFn: () => fetchMemoryDrillDown("chunk-1"), retry: false });
  const scoring = useQuery({ queryKey: ["memory-tree-scoring"], queryFn: fetchMemoryTreeScoring, retry: false });
  if (search.isLoading || sourceTree.isLoading || topicTree.isLoading || daily.isLoading || drillDown.isLoading || scoring.isLoading) return <InlineState message="Loading memory tree projections..." />;
  for (const query of [search, sourceTree, topicTree, daily, drillDown, scoring]) {
    if (query.isError) return <InlineState message={query.error.message} />;
  }
  const sourceNodes = Array.isArray(sourceTree.data?.tree.nodes) ? sourceTree.data.tree.nodes as Record<string, unknown>[] : [];
  const topicNodes = Array.isArray(topicTree.data?.tree.nodes) ? topicTree.data.tree.nodes as Record<string, unknown>[] : [];
  return <div className="space-y-4"><SafeTable title="Memory Tree Search" rows={search.data?.results ?? []} empty="No memory tree results." /><SafeTable title="Source Tree" rows={sourceNodes} empty="No source tree nodes." /><SafeTable title="Topic Tree" rows={topicNodes} empty="No topic tree nodes." /><SafeTable title="Daily Digest" rows={daily.data ? [daily.data.daily_digest] : []} empty="No daily digest." /><SafeTable title="Evidence Drill-Down" rows={drillDown.data ? [drillDown.data.evidence] : []} empty="No evidence drill-down." /><SafeTable title="Scoring Explanation" rows={scoring.data?.scores ?? []} empty="No scoring summaries." /></div>;
}
