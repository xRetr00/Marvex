import { useEffect, useState } from "react";
import { listen } from "../lib/tauriBridge";
import { Check, ShieldAlert, X } from "lucide-react";
import { decideApproval, fetchPendingApprovals, type ApprovalSummary } from "../lib/controlPlaneClient";

type SpotlightPayload =
  | { kind: "info"; title: string; body: string }
  | { kind: "result"; title: string; body: string }
  | { kind: "approval"; approval: ApprovalSummary };

export function SpotlightSurface() {
  const [payload, setPayload] = useState<SpotlightPayload>({ kind: "info", title: "Marvex", body: "Waiting for assistant activity." });
  const [pending, setPending] = useState(false);

  useEffect(() => {
    void fetchPendingApprovals().then((approvals) => {
      if (approvals[0]) setPayload({ kind: "approval", approval: approvals[0] });
    }).catch(() => undefined);
    const unlisten = listen<SpotlightPayload>("spotlight-payload", (event) => setPayload(event.payload));
    const voiceDecision = listen<{ approval_id: string; decision: "approve" | "deny" | "cancel"; reason?: string }>("approval-voice-decision", async (event) => {
      setPending(true);
      try {
        await decideApproval(event.payload.approval_id, event.payload.decision, event.payload.reason ?? "voice approval decision");
      } finally {
        setPending(false);
      }
    });
    return () => {
      void unlisten.then((fn) => fn());
      void voiceDecision.then((fn) => fn());
    };
  }, []);

  if (payload.kind === "approval") {
    return <ApprovalCard approval={payload.approval} pending={pending} setPending={setPending} />;
  }

  return (
    <main className="spotlight-shell">
      <section className="spotlight-panel">
        <h1>{payload.title}</h1>
        <p>{payload.body}</p>
      </section>
    </main>
  );
}

function ApprovalCard({ approval, pending, setPending }: { approval: ApprovalSummary; pending: boolean; setPending: (value: boolean) => void }) {
  async function decide(decision: "approve" | "deny" | "cancel") {
    setPending(true);
    try {
      await decideApproval(approval.approval_request_id, decision, `spotlight ${decision}`);
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="spotlight-shell">
      <section className="spotlight-panel approval-panel">
        <div className="approval-kicker"><ShieldAlert size={18} /> Approval Required</div>
        <h1>{approval.user_visible_summary}</h1>
        <p>Risk level: {approval.risk_level}</p>
        <div className="approval-actions">
          <button disabled={pending} onClick={() => void decide("approve")}><Check size={16} /> Approve</button>
          <button disabled={pending} onClick={() => void decide("deny")}><X size={16} /> Deny</button>
          <button disabled={pending} onClick={() => void decide("cancel")}>Cancel</button>
        </div>
      </section>
    </main>
  );
}
