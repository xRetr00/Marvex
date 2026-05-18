import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ShieldAlert } from "lucide-react";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { decideApproval } from "../lib/api";
import type { ApprovalSummary } from "../lib/schemas";

export function Approvals({ approvals }: { approvals: ApprovalSummary[] }) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("Reviewed in local control plane");
  const mutation = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "approve" | "deny" }) => decideApproval(id, decision, reason),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["control-snapshot"] });
      void queryClient.invalidateQueries({ queryKey: ["approvals"] });
    }
  });

  if (!approvals.length) {
    return <Empty title="No pending approvals" detail="Risky actions will pause here before any backend execution can proceed." />;
  }

  return (
    <div className="space-y-3">
      <label className="block text-sm font-medium">Decision reason</label>
      <input className="h-9 w-full max-w-xl rounded-md border border-border bg-card px-3" value={reason} onChange={(event) => setReason(event.target.value)} />
      {approvals.map((approval) => (
        <Card key={approval.approval_request_id}>
          <CardHeader>
            <CardTitle className="flex flex-wrap items-center gap-2"><ShieldAlert size={18} /> {approval.capability_summary.identifier} <Badge tone={approval.risk_level}>{approval.risk_level}</Badge></CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 lg:grid-cols-[1fr_auto]">
            <div className="space-y-2 text-sm">
              <p>{approval.user_visible_summary}</p>
              <div className="grid gap-2 md:grid-cols-3">
                <span>Mode: {approval.execution_mode}</span>
                <span>Side effect: {approval.side_effect_level}</span>
                <span>Status: {approval.status}</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" disabled={mutation.isPending} onClick={() => mutation.mutate({ id: approval.approval_request_id, decision: "deny" })}>Deny</Button>
              <Button disabled={mutation.isPending} onClick={() => mutation.mutate({ id: approval.approval_request_id, decision: "approve" })}>Approve</Button>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function Empty({ title, detail }: { title: string; detail: string }) {
  return <Card><CardContent className="p-6"><div className="font-medium">{title}</div><p className="mt-1 text-sm text-muted-foreground">{detail}</p></CardContent></Card>;
}