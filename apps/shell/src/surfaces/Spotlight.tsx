import { useEffect, useState } from "react";
import { listen } from "../lib/tauriBridge";
import { decideApproval, fetchPendingApprovals, type ApprovalSummary } from "../lib/controlPlaneClient";
import { motion, AnimatePresence } from "framer-motion";
import { ShieldAlert, Check, X, Loader2 } from "lucide-react";

type SpotlightPayload =
  | { kind: "info"; title: string; body: string }
  | { kind: "result"; title: string; body: string }
  | { kind: "approval"; approval: ApprovalSummary };

export function SpotlightSurface() {
  const [payload, setPayload] = useState<SpotlightPayload>({
    kind: "info",
    title: "Marvex",
    body: "Waiting for assistant activity.",
  });
  const [pending, setPending] = useState(false);

  useEffect(() => {
    void fetchPendingApprovals()
      .then((approvals) => {
        if (approvals[0]) setPayload({ kind: "approval", approval: approvals[0] });
      })
      .catch(() => undefined);

    const unlisten = listen<SpotlightPayload>("spotlight-payload", (event) =>
      setPayload(event.payload),
    );
    const voiceDecision = listen<{
      approval_id: string;
      decision: "approve" | "deny" | "cancel";
      reason?: string;
    }>("approval-voice-decision", async (event) => {
      setPending(true);
      try {
        await decideApproval(
          event.payload.approval_id,
          event.payload.decision,
          event.payload.reason ?? "voice approval decision",
        );
      } finally {
        setPending(false);
      }
    });

    return () => {
      void unlisten.then((fn) => fn());
      void voiceDecision.then((fn) => fn());
    };
  }, []);

  return (
    <main className="spotlight-shell">
      <AnimatePresence mode="wait">
        {payload.kind === "approval" ? (
          <motion.div
            key="approval"
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ type: "spring", duration: 0.4, bounce: 0.15 }}
          >
            <ApprovalCard
              approval={payload.approval}
              pending={pending}
              setPending={setPending}
            />
          </motion.div>
        ) : (
          <motion.section
            key="info"
            className="spotlight-panel"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            transition={{ type: "spring", duration: 0.4, bounce: 0.1 }}
          >
            <h1 style={{ color: "white", fontSize: "1.1rem", fontWeight: 600, margin: 0 }}>
              {payload.title}
            </h1>
            <p style={{ color: "rgba(255,255,255,0.6)", fontSize: "0.85rem", margin: "6px 0 0" }}>
              {payload.body}
            </p>
          </motion.section>
        )}
      </AnimatePresence>
    </main>
  );
}

function ApprovalCard({
  approval,
  pending,
  setPending,
}: {
  approval: ApprovalSummary;
  pending: boolean;
  setPending: (value: boolean) => void;
}) {
  async function decide(decision: "approve" | "deny" | "cancel") {
    setPending(true);
    try {
      await decideApproval(
        approval.approval_request_id,
        decision,
        `spotlight ${decision}`,
      );
    } finally {
      setPending(false);
    }
  }

  const riskColor =
    approval.risk_level === "high"
      ? "#ef4444"
      : approval.risk_level === "medium"
        ? "#f97316"
        : "#22c55e";

  return (
    <section
      className="spotlight-panel approval-panel"
      style={{
        background: "rgba(255,255,255,0.04)",
        border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: "16px",
        padding: "20px",
        display: "flex",
        flexDirection: "column",
        gap: "12px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          color: "#f97316",
          fontSize: "0.75rem",
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
        }}
      >
        <ShieldAlert size={15} />
        Approval Required
      </div>

      <h1 style={{ color: "white", fontSize: "1rem", fontWeight: 600, margin: 0 }}>
        {approval.user_visible_summary}
      </h1>

      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
        <span style={{ color: "rgba(255,255,255,0.4)", fontSize: "0.75rem" }}>Risk:</span>
        <span
          style={{
            color: riskColor,
            fontSize: "0.75rem",
            fontWeight: 600,
            textTransform: "capitalize",
            background: `${riskColor}22`,
            padding: "2px 8px",
            borderRadius: "20px",
          }}
        >
          {approval.risk_level}
        </span>
      </div>

      <div style={{ display: "flex", gap: "8px", marginTop: "4px" }}>
        <button
          disabled={pending}
          onClick={() => void decide("approve")}
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "6px",
            padding: "8px 12px",
            background: "rgba(34,197,94,0.15)",
            border: "1px solid rgba(34,197,94,0.3)",
            borderRadius: "8px",
            color: "#22c55e",
            fontSize: "0.8rem",
            fontWeight: 600,
            cursor: pending ? "not-allowed" : "pointer",
            opacity: pending ? 0.5 : 1,
          }}
        >
          {pending ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
          Approve
        </button>
        <button
          disabled={pending}
          onClick={() => void decide("deny")}
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "6px",
            padding: "8px 12px",
            background: "rgba(239,68,68,0.15)",
            border: "1px solid rgba(239,68,68,0.3)",
            borderRadius: "8px",
            color: "#ef4444",
            fontSize: "0.8rem",
            fontWeight: 600,
            cursor: pending ? "not-allowed" : "pointer",
            opacity: pending ? 0.5 : 1,
          }}
        >
          <X size={14} />
          Deny
        </button>
        <button
          disabled={pending}
          onClick={() => void decide("cancel")}
          style={{
            padding: "8px 12px",
            background: "rgba(255,255,255,0.06)",
            border: "1px solid rgba(255,255,255,0.12)",
            borderRadius: "8px",
            color: "rgba(255,255,255,0.5)",
            fontSize: "0.8rem",
            fontWeight: 500,
            cursor: pending ? "not-allowed" : "pointer",
            opacity: pending ? 0.5 : 1,
          }}
        >
          Cancel
        </button>
      </div>
    </section>
  );
}
