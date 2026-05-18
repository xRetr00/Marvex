import { cn } from "../../lib/utils";

type BadgeTone = "neutral" | "safe" | "low" | "medium" | "high" | "critical" | "success";

const tones: Record<BadgeTone, string> = {
  neutral: "border-border bg-muted text-foreground",
  safe: "border-emerald-200 bg-emerald-50 text-emerald-800",
  low: "border-sky-200 bg-sky-50 text-sky-800",
  medium: "border-amber-200 bg-amber-50 text-amber-800",
  high: "border-orange-200 bg-orange-50 text-orange-900",
  critical: "border-red-200 bg-red-50 text-red-900",
  success: "border-emerald-200 bg-emerald-50 text-emerald-800"
};

export function Badge({ tone = "neutral", children, className }: { tone?: BadgeTone; children: React.ReactNode; className?: string }) {
  return <span className={cn("inline-flex items-center rounded px-2 py-0.5 text-xs font-medium border", tones[tone], className)}>{children}</span>;
}