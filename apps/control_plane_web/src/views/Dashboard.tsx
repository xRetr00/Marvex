import { Activity, Brain, CheckCircle2, Server, ShieldCheck, Wrench } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import type { ControlSnapshot } from "../lib/schemas";

function metric(label: string, value: number | string, icon: React.ReactNode) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between gap-3 p-4">
        <div>
          <div className="text-xs text-muted-foreground">{label}</div>
          <div className="mt-1 text-2xl font-semibold">{value}</div>
        </div>
        <div className="text-primary">{icon}</div>
      </CardContent>
    </Card>
  );
}

export function Dashboard({ snapshot }: { snapshot: ControlSnapshot }) {
  const pending = snapshot.approvals?.pending_count ?? 0;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
        {metric("Pending approvals", pending, <ShieldCheck size={22} />)}
        {metric("Providers", snapshot.providers.length, <Server size={22} />)}
        {metric("Capabilities", snapshot.capabilities.length, <Wrench size={22} />)}
        {metric("Traces", snapshot.traces.length, <Activity size={22} />)}
        {metric("Skills", snapshot.skills.length, <Brain size={22} />)}
        {metric("Raw persistence", snapshot.raw_payload_persisted ? "on" : "off", <CheckCircle2 size={22} />)}
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Runtime posture</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-3">
          <div className="rounded-md border border-border p-3"><div className="text-xs text-muted-foreground">Policy authority</div><div className="mt-1 font-medium">CapabilityRuntime</div></div>
          <div className="rounded-md border border-border p-3"><div className="text-xs text-muted-foreground">Frontend access</div><div className="mt-1 font-medium">Local API only</div></div>
          <div className="rounded-md border border-border p-3"><div className="text-xs text-muted-foreground">Risk state</div><div className="mt-1"><Badge tone={pending ? "high" : "success"}>{pending ? "approval required" : "clear"}</Badge></div></div>
        </CardContent>
      </Card>
    </div>
  );
}