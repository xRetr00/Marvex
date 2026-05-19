import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Mic, Search, ShieldAlert, Trash2, Volume2 } from "lucide-react";
import {
  applyLearningCandidate,
  downloadVoiceModel,
  enableSkill,
  fetchVoiceWorkerDevices,
  fetchVoiceWorkerStatus,
  fetchApprovalHistory,
  fetchAutoFetch,
  fetchMemoryDailyDigest,
  fetchMemoryDrillDown,
  fetchConnectors,
  fetchDiagnostics,
  fetchFeedbackEvents,
  fetchLearningCandidates,
  fetchMcpMarketplace,
  fetchMemoryInspect,
  fetchMemorySourceTree,
  fetchMemoryTopicTree,
  fetchMemoryTreeScoring,
  fetchMemoryTreeSearch,
  fetchPolicies,
  fetchRuntimePolicy,
  fetchRuntimePolicyAudit,
  fetchVoiceStatus,
  fetchSources,
  forgetSource,
  fetchSkillsMarketplace,
  fetchTraceSearch,
  forgetMemory,
  proposeMcpAllowlist,
  removeVoiceModel,
  setRuntimePolicyMode,
  selectVoiceStt,
  selectVoiceTts,
  setAutoFetchState,
  startVoiceWorker,
  stopVoiceWorker,
  pauseVoiceWorker,
  resumeVoiceWorker,
  testVoiceStt,
  testVoiceTts,
  testVoiceWorkerMic,
  testVoiceWorkerPlayback,
  updateVoiceBargeIn,
  updateVoiceEarlySpeech,
  updateVoicePersonality,
  updateVoiceRetention,
  updateVoiceVad,
  updateWakeword
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

export function FeedbackLearningView() {
  const queryClient = useQueryClient();
  const feedback = useQuery({ queryKey: ["feedback-events"], queryFn: fetchFeedbackEvents, retry: false });
  const candidates = useQuery({ queryKey: ["learning-candidates"], queryFn: fetchLearningCandidates, retry: false });
  const mutation = useMutation({
    mutationFn: applyLearningCandidate,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["learning-candidates"] })
  });
  if (feedback.isLoading || candidates.isLoading) return <InlineState message="Loading feedback and learning candidates..." />;
  if (feedback.isError) return <InlineState message={feedback.error.message} />;
  if (candidates.isError) return <InlineState message={candidates.error.message} />;
  const candidateRows: Record<string, unknown>[] = [
    ...(candidates.data?.memory_candidates ?? []).map((row) => ({ ...row, candidate_type: "memory" })),
    ...(candidates.data?.skill_candidates ?? []).map((row) => ({ ...row, candidate_type: "skill" })),
    ...(candidates.data?.policy_candidates ?? []).map((row) => ({ ...row, candidate_type: "policy" })),
    ...(candidates.data?.preference_candidates ?? []).map((row) => ({ ...row, candidate_type: "preference" })),
    ...(candidates.data?.route_candidates ?? []).map((row) => ({ ...row, candidate_type: "route" }))
  ];
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>Feedback / Learning</CardTitle></CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {candidateRows.map((row) => <Button key={String(row.candidate_id ?? `${row.candidate_type}-${row.input_summary}`)} variant="outline" onClick={() => mutation.mutate(String(row.candidate_id))} disabled={!row.candidate_id}><CheckCircle2 className="mr-2" size={16} />Apply {String(row.candidate_id ?? row.candidate_type)}</Button>)}
          {mutation.data && <span className="text-sm text-muted-foreground">Apply status: {String(mutation.data.status)}</span>}
        </CardContent>
      </Card>
      <SafeTable title="Feedback Events" rows={feedback.data?.events ?? []} empty="No feedback events available." />
      <SafeTable title="Learning Candidates" rows={candidateRows} empty="No learning candidates available." />
      <SafeTable title="Memory Scoring Changes" rows={candidates.data?.memory_scoring_changes ?? []} empty="No memory scoring changes available." />
    </div>
  );
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

export function RuntimePolicyView() {
  const queryClient = useQueryClient();
  const policy = useQuery({ queryKey: ["runtime-policy"], queryFn: fetchRuntimePolicy, retry: false });
  const audit = useQuery({ queryKey: ["runtime-policy-audit"], queryFn: fetchRuntimePolicyAudit, retry: false });
  const mutation = useMutation({
    mutationFn: setRuntimePolicyMode,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["runtime-policy"] });
      queryClient.invalidateQueries({ queryKey: ["runtime-policy-audit"] });
    }
  });
  if (policy.isLoading || audit.isLoading) return <InlineState message="Loading runtime policy controls..." />;
  if (policy.isError) return <InlineState message={policy.error.message} />;
  if (audit.isError) return <InlineState message={audit.error.message} />;
  const matrixRows = Object.entries(policy.data?.matrix ?? {}).map(([capability, permission]) => ({ capability, permission, policy_controlled: true }));
  const auditRows = (audit.data?.audit_records?.length ? audit.data.audit_records : policy.data?.audit_records) ?? [];
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>Runtime Policy / Autonomy Modes</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-[260px_1fr]">
          <label className="grid gap-1 text-sm font-medium" htmlFor="autonomy-mode">
            Autonomy mode
            <select id="autonomy-mode" className="h-9 rounded-md border border-input bg-background px-3 text-sm" value={String(policy.data?.mode ?? "ask_before_risky")} onChange={(event) => mutation.mutate(event.target.value)}>
              <option value="locked_down">Locked Down</option>
              <option value="ask_before_risky">Ask Before Risky</option>
              <option value="auto_marvex">Auto Marvex</option>
              <option value="custom">Custom</option>
            </select>
          </label>
          <div className="text-sm text-muted-foreground">
            Hard-block is reserved for blacklist abuse only. Normal assistant actions are allow, ask, deny, or quarantine through backend policy.
          </div>
        </CardContent>
      </Card>
      <SafeTable title="Capability Permission Matrix" rows={matrixRows} empty="No runtime policy matrix available." />
      <SafeTable title="Policy Decision Audit" rows={auditRows} empty="No policy decisions recorded." />
    </div>
  );
}

export function VoiceRuntimeView() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["voice-runtime"], queryFn: fetchVoiceStatus, retry: false });
  const workerQuery = useQuery({ queryKey: ["voice-worker"], queryFn: fetchVoiceWorkerStatus, retry: false });
  const devicesQuery = useQuery({ queryKey: ["voice-worker-devices"], queryFn: fetchVoiceWorkerDevices, retry: false });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["voice-runtime"] });
  const refreshWorker = () => {
    queryClient.invalidateQueries({ queryKey: ["voice-worker"] });
    queryClient.invalidateQueries({ queryKey: ["voice-worker-devices"] });
  };
  const stt = useMutation({ mutationFn: () => selectVoiceStt({ main_backend_id: "moonshine-v2", fallback_backend_id: "sensevoice-small" }), onSuccess: refresh });
  const tts = useMutation({ mutationFn: () => selectVoiceTts({ main_backend_id: "kokoro-onnx", fallback_backend_id: "piper-tts", active_voice_id: "af_heart" }), onSuccess: refresh });
  const wakeword = useMutation({ mutationFn: () => updateWakeword(true), onSuccess: refresh });
  const vad = useMutation({ mutationFn: updateVoiceVad, onSuccess: refresh });
  const bargeIn = useMutation({ mutationFn: updateVoiceBargeIn, onSuccess: refresh });
  const earlySpeech = useMutation({ mutationFn: updateVoiceEarlySpeech, onSuccess: refresh });
  const personality = useMutation({ mutationFn: updateVoicePersonality, onSuccess: refresh });
  const retention = useMutation({ mutationFn: updateVoiceRetention, onSuccess: refresh });
  const download = useMutation({ mutationFn: () => downloadVoiceModel({ model_id: "af_heart", backend_id: "kokoro-onnx", model_kind: "tts_voice", source_uri: "local://voices/af_heart" }), onSuccess: refresh });
  const remove = useMutation({ mutationFn: () => removeVoiceModel({ model_id: "af_heart", model_kind: "tts_voice" }), onSuccess: refresh });
  const sttTest = useMutation({ mutationFn: testVoiceStt });
  const ttsTest = useMutation({ mutationFn: testVoiceTts });
  const workerStart = useMutation({ mutationFn: startVoiceWorker, onSuccess: refreshWorker });
  const workerStop = useMutation({ mutationFn: stopVoiceWorker, onSuccess: refreshWorker });
  const workerPause = useMutation({ mutationFn: pauseVoiceWorker, onSuccess: refreshWorker });
  const workerResume = useMutation({ mutationFn: resumeVoiceWorker, onSuccess: refreshWorker });
  const workerMic = useMutation({ mutationFn: testVoiceWorkerMic, onSuccess: refreshWorker });
  const workerPlayback = useMutation({ mutationFn: testVoiceWorkerPlayback, onSuccess: refreshWorker });
  if (query.isLoading) return <InlineState message="Loading voice runtime controls..." />;
  if (query.isError) return <InlineState message={query.error.message} />;
  const data = query.data ?? {};
  const summary = typeof data.summary === "object" && data.summary ? data.summary as Record<string, unknown> : {};
  const settings = typeof data.settings === "object" && data.settings ? data.settings as Record<string, unknown> : {};
  const backends = typeof data.backends === "object" && data.backends ? data.backends as Record<string, unknown> : {};
  const telemetry = typeof data.telemetry === "object" && data.telemetry ? data.telemetry as Record<string, unknown> : {};
  const backendRows = Array.isArray(backends.backend_health) ? backends.backend_health as Record<string, unknown>[] : [];
  const worker = typeof workerQuery.data === "object" && workerQuery.data ? workerQuery.data as Record<string, unknown> : {};
  const devices = typeof devicesQuery.data === "object" && devicesQuery.data ? devicesQuery.data as Record<string, unknown> : {};
  const inputDevices = Array.isArray(devices.input_devices) ? devices.input_devices as Record<string, unknown>[] : [];
  const outputDevices = Array.isArray(devices.output_devices) ? devices.output_devices as Record<string, unknown>[] : [];
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>Voice Worker Process</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <Button variant="outline" onClick={() => workerStart.mutate()}><Mic className="mr-2" size={16} />Start Worker</Button>
          <Button variant="outline" onClick={() => workerPause.mutate()}>Pause Worker</Button>
          <Button variant="outline" onClick={() => workerResume.mutate()}>Resume Worker</Button>
          <Button variant="outline" onClick={() => workerStop.mutate()}>Stop Worker</Button>
          <Button variant="outline" onClick={() => workerMic.mutate()}>Test Mic Level</Button>
          <Button variant="outline" onClick={() => workerPlayback.mutate()}><Volume2 className="mr-2" size={16} />Test Playback</Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Voice Runtime</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <Button variant="outline" onClick={() => stt.mutate()}><Mic className="mr-2" size={16} />Use Moonshine / SenseVoice</Button>
          <Button variant="outline" onClick={() => tts.mutate()}><Volume2 className="mr-2" size={16} />Use Kokoro / Piper</Button>
          <Button variant="outline" onClick={() => wakeword.mutate()}><Mic className="mr-2" size={16} />Enable Hey Marvex</Button>
          <Button variant="outline" onClick={() => vad.mutate()}>Set VAD</Button>
          <Button variant="outline" onClick={() => bargeIn.mutate()}>Set Barge-In</Button>
          <Button variant="outline" onClick={() => earlySpeech.mutate()}>Set Early Speech</Button>
          <Button variant="outline" onClick={() => personality.mutate()}>Set Personality</Button>
          <Button variant="outline" onClick={() => retention.mutate()}>Set Retention</Button>
          <Button variant="outline" onClick={() => download.mutate()}>Install af_heart</Button>
          <Button variant="outline" onClick={() => remove.mutate()}><Trash2 className="mr-2" size={16} />Remove af_heart</Button>
          <Button variant="outline" onClick={() => sttTest.mutate()}>Test STT</Button>
          <Button variant="outline" onClick={() => ttsTest.mutate()}>Test TTS</Button>
        </CardContent>
      </Card>
      <SafeTable title="Voice Runtime Status" rows={[summary]} empty="No voice status." />
      <SafeTable title="Voice Worker Status" rows={[worker]} empty="No voice worker status." />
      <SafeTable title="Microphone Devices" rows={inputDevices} empty="No microphone devices reported." />
      <SafeTable title="Playback Devices" rows={outputDevices} empty="No playback devices reported." />
      <SafeTable title="STT / TTS / Wakeword / VAD Backends" rows={backendRows} empty="No backend health." />
      <SafeTable title="Wakeword / VAD / Barge-In / Early Speech / Personality" rows={[settings]} empty="No voice settings." />
      <SafeTable title="Voice Telemetry Summary" rows={[telemetry]} empty="No voice telemetry." />
      <SafeTable title="Last Voice Action" rows={[stt.data, tts.data, wakeword.data, vad.data, bargeIn.data, earlySpeech.data, personality.data, retention.data, download.data, remove.data, sttTest.data, ttsTest.data, workerStart.data, workerStop.data, workerPause.data, workerResume.data, workerMic.data, workerPlayback.data].filter(Boolean) as Record<string, unknown>[]} empty="No voice action run." />
    </div>
  );
}
