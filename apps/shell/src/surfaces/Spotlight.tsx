import { useEffect, useState } from "react";
import { listen } from "../lib/tauriBridge";
import { decideApproval, fetchPendingApprovals, type ApprovalSummary } from "../lib/controlPlaneClient";
import type { TurnStage } from "../lib/localTurn";
import { motion, AnimatePresence } from "framer-motion";
import { ShieldAlert, ListTodo, Bell } from "lucide-react";
import { RichMessage } from "@/components/marvex/RichMessage";
import {
  Confirmation,
  ConfirmationTitle,
  ConfirmationActions,
  ConfirmationAction,
  ConfirmationAccepted,
  ConfirmationRejected,
} from "@/components/confirmation";
import { AlertBadge } from "@/components/alert-badge";
import { Task, TaskTrigger, TaskContent, TaskItem } from "@/components/task";
import {
  Queue,
  QueueSection,
  QueueSectionTrigger,
  QueueSectionLabel,
  QueueSectionContent,
  QueueList,
  QueueItem,
  QueueItemIndicator,
  QueueItemContent,
} from "@/components/queue";

interface AgendaItem {
  title: string;
  done?: boolean;
}

type SpotlightPayload =
  | { kind: "info"; title: string; body: string }
  | { kind: "result"; title?: string; body: string; stages?: TurnStage[] }
  | { kind: "agenda"; title?: string; tasks?: AgendaItem[]; reminders?: string[] }
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

    const unlisten = listen<SpotlightPayload>("spotlight-payload", (event) => setPayload(event.payload));
    const voiceDecision = listen<{ approval_id: string; decision: "approve" | "deny" | "cancel"; reason?: string }>(
      "approval-voice-decision",
      async (event) => {
        setPending(true);
        try {
          await decideApproval(event.payload.approval_id, event.payload.decision, event.payload.reason ?? "voice approval decision");
        } finally {
          setPending(false);
        }
      },
    );

    return () => {
      void unlisten.then((fn) => fn());
      void voiceDecision.then((fn) => fn());
    };
  }, []);

  return (
    <main className="spotlight-shell">
      <AnimatePresence mode="wait">
        <motion.section
          key={payload.kind}
          className="spotlight-panel"
          initial={{ opacity: 0, scale: 0.97, y: 8 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.97, y: 8 }}
          transition={{ type: "spring", duration: 0.4, bounce: 0.12 }}
        >
          {payload.kind === "approval" && <ApprovalView approval={payload.approval} pending={pending} setPending={setPending} />}
          {payload.kind === "result" && <RichMessage text={payload.body} stages={payload.stages} />}
          {payload.kind === "agenda" && <AgendaView title={payload.title} tasks={payload.tasks ?? []} reminders={payload.reminders ?? []} />}
          {payload.kind === "info" && (
            <>
              <h1>{payload.title}</h1>
              <p>{payload.body}</p>
            </>
          )}
        </motion.section>
      </AnimatePresence>
    </main>
  );
}

function AgendaView({ title, tasks, reminders }: { title?: string; tasks: AgendaItem[]; reminders: string[] }) {
  const remaining = tasks.filter((t) => !t.done).length;
  return (
    <div className="flex flex-col gap-4">
      {title && <h1>{title}</h1>}
      {reminders.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {reminders.map((r, i) => (
            <AlertBadge key={`rem-${i}`} variant="info" icon={Bell} label={r} />
          ))}
        </div>
      )}
      {tasks.length > 0 && (
        <Task defaultOpen className="rounded-lg border border-border p-2">
          <TaskTrigger title={`Tasks (${remaining} open)`} />
          <TaskContent>
            {tasks.map((t, i) => (
              <TaskItem key={`task-${i}`}>{t.done ? "✓ " : "• "}{t.title}</TaskItem>
            ))}
          </TaskContent>
        </Task>
      )}
      {tasks.length > 0 && (
        <Queue>
          <QueueSection defaultOpen>
            <QueueSectionTrigger>
              <QueueSectionLabel label="Queue" count={tasks.length} icon={<ListTodo className="size-4" />} />
            </QueueSectionTrigger>
            <QueueSectionContent>
              <QueueList>
                {tasks.map((t, i) => (
                  <QueueItem key={`q-${i}`}>
                    <QueueItemIndicator completed={t.done} />
                    <QueueItemContent completed={t.done}>{t.title}</QueueItemContent>
                  </QueueItem>
                ))}
              </QueueList>
            </QueueSectionContent>
          </QueueSection>
        </Queue>
      )}
    </div>
  );
}

function ApprovalView({
  approval,
  pending,
  setPending,
}: {
  approval: ApprovalSummary;
  pending: boolean;
  setPending: (value: boolean) => void;
}) {
  const [approved, setApproved] = useState<boolean | undefined>(undefined);
  const responded = approved !== undefined;

  async function decide(decision: "approve" | "deny" | "cancel") {
    setPending(true);
    try {
      await decideApproval(approval.approval_request_id, decision, `spotlight ${decision}`);
      if (decision !== "cancel") setApproved(decision === "approve");
    } finally {
      setPending(false);
    }
  }

  const riskColor = approval.risk_level === "high" ? "#ef4444" : approval.risk_level === "medium" ? "#f97316" : "#22c55e";

  const approvalData = approved === undefined
    ? { id: approval.approval_request_id }
    : { id: approval.approval_request_id, approved };

  return (
    <Confirmation
      approval={approvalData}
      state={responded ? "approval-responded" : "approval-requested"}
      className="border-orange-500/30 bg-card"
    >
      <div className="flex items-center gap-2 text-orange-400 text-xs font-semibold uppercase tracking-wider">
        <ShieldAlert size={15} /> Approval Required
      </div>
      <ConfirmationTitle>
        <span className="font-semibold text-foreground">{approval.user_visible_summary}</span>
        <span className="ml-2" style={{ color: riskColor }}>
          ({approval.risk_level} risk)
        </span>
      </ConfirmationTitle>
      <ConfirmationActions>
        <ConfirmationAction disabled={pending} onClick={() => void decide("approve")}>Approve</ConfirmationAction>
        <ConfirmationAction disabled={pending} variant="outline" onClick={() => void decide("deny")}>Deny</ConfirmationAction>
        <ConfirmationAction disabled={pending} variant="ghost" onClick={() => void decide("cancel")}>Cancel</ConfirmationAction>
      </ConfirmationActions>
      <ConfirmationAccepted>
        <span className="text-sm text-emerald-400">Approved.</span>
      </ConfirmationAccepted>
      <ConfirmationRejected>
        <span className="text-sm text-red-400">Denied.</span>
      </ConfirmationRejected>
    </Confirmation>
  );
}
