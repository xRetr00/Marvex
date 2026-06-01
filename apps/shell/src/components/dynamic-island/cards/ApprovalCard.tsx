import { useState } from "react";
import { decideApproval, type ApprovalSummary } from "@/lib/controlPlaneClient";
import { resumeApprovalTurn } from "@/lib/shellCommands";

type Decision = "approve" | "deny";

export interface ApprovalCardProps {
  approval: ApprovalSummary;
  /** Called once the decision has been submitted (and the turn resumed if possible). */
  onDone: () => void;
}

// Inline approval surface shown inside the expanded island. The decision is always
// POSTed to the control plane; the turn is *additionally* resumed when the backend
// supplied trace/turn ids. Buttons are only disabled while a decision is in flight —
// missing ids never leave them permanently dead.
export function ApprovalCard({ approval, onDone }: ApprovalCardProps) {
  const [pending, setPending] = useState(false);

  const decide = async (decision: Decision) => {
    setPending(true);
    try {
      await decideApproval(approval.approval_request_id, decision, `dynamic island ${decision}`);
      if (approval.trace_id && approval.turn_id) {
        await resumeApprovalTurn({
          text: approval.user_visible_summary,
          traceId: approval.trace_id,
          turnId: approval.turn_id,
          approvalId: approval.approval_request_id,
          decision,
        });
      }
      onDone();
    } finally {
      setPending(false);
    }
  };

  return (
    <div role="group" aria-label="Approval required" style={rootStyle}>
      <div style={headerStyle}>
        <span aria-hidden style={iconStyle}>!</span>
        <div style={{ minWidth: 0 }}>
          <div style={titleStyle}>Approval Required</div>
          <div style={bodyStyle}>{approval.user_visible_summary}</div>
        </div>
      </div>
      <div style={actionsStyle}>
        <button type="button" disabled={pending} onClick={(e) => { e.stopPropagation(); void decide("approve"); }} style={{ ...btnStyle, ...approveStyle }}>
          Approve
        </button>
        <button type="button" disabled={pending} onClick={(e) => { e.stopPropagation(); void decide("deny"); }} style={{ ...btnStyle, ...denyStyle }}>
          Deny
        </button>
      </div>
    </div>
  );
}

const rootStyle: React.CSSProperties = { display: "flex", flexDirection: "column", gap: 10, width: "100%" };
const headerStyle: React.CSSProperties = { display: "flex", alignItems: "flex-start", gap: 10 };
const iconStyle: React.CSSProperties = {
  width: 28, height: 28, flexShrink: 0, borderRadius: 999, display: "grid", placeItems: "center",
  background: "rgba(255,224,194,0.10)", boxShadow: "inset 0 0 0 1px rgba(255,224,194,0.18)",
  color: "#ffe0c2", fontWeight: 800, fontSize: 14,
};
const titleStyle: React.CSSProperties = { fontSize: 13, fontWeight: 650, letterSpacing: "-0.01em", color: "#fff" };
const bodyStyle: React.CSSProperties = { marginTop: 2, fontSize: 11.5, lineHeight: "15px", color: "rgba(255,255,255,0.6)", overflowWrap: "anywhere" };
const actionsStyle: React.CSSProperties = { display: "flex", gap: 8, justifyContent: "flex-end" };
const btnStyle: React.CSSProperties = {
  border: 0, borderRadius: 999, padding: "5px 14px", fontSize: 11.5, fontWeight: 650,
  cursor: "pointer", whiteSpace: "nowrap",
};
const approveStyle: React.CSSProperties = { background: "rgba(52,199,89,0.16)", boxShadow: "inset 0 0 0 1px rgba(52,199,89,0.24)", color: "#7afca0" };
const denyStyle: React.CSSProperties = { background: "rgba(229,77,46,0.15)", boxShadow: "inset 0 0 0 1px rgba(229,77,46,0.22)", color: "#ff9a87" };
