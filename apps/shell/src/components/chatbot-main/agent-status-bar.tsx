import { AnimatePresence, motion } from "framer-motion";
import { Brain, Globe, Wrench, Mic, Volume2, AlertTriangle, Cpu } from "lucide-react";
import type { AssistantStatusKind } from "@/lib/assistantState";
import { statusLabel } from "@/lib/assistantState";

const STATUS_ICON: Partial<Record<AssistantStatusKind, React.ElementType>> = {
  thinking: Brain,
  working: Cpu,
  using_tools: Wrench,
  mcp: Wrench,
  skills: Cpu,
  searching_web: Globe,
  listening: Mic,
  talking: Volume2,
  needs_approval: AlertTriangle,
  asking: AlertTriangle,
};

const STATUS_COLOR: Partial<Record<AssistantStatusKind, string>> = {
  thinking: "var(--muted-foreground)",
  working: "var(--muted-foreground)",
  using_tools: "#f59e0b",
  mcp: "#f59e0b",
  skills: "#a78bfa",
  searching_web: "#38bdf8",
  listening: "#34d399",
  talking: "#34d399",
  needs_approval: "var(--destructive)",
  asking: "var(--destructive)",
};

interface AgentStatusBarProps {
  status: AssistantStatusKind;
  pending: boolean;
}

export function AgentStatusBar({ status, pending }: AgentStatusBarProps) {
  const active = pending || status !== "idle";
  const Icon = STATUS_ICON[status];
  const color = STATUS_COLOR[status] ?? "var(--muted-foreground)";

  return (
    <AnimatePresence>
      {active && (
        <motion.div
          key="agent-status-bar"
          className="marvex-agent-status-bar"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          role="status"
          aria-live="polite"
          aria-label={`Agent status: ${statusLabel(status)}`}
        >
          <span className="marvex-agent-status-indicator" style={{ background: color }} />
          {Icon && <Icon size={12} style={{ color, flexShrink: 0 }} />}
          <span className="marvex-agent-status-label" style={{ color }}>
            {statusLabel(status)}
          </span>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
